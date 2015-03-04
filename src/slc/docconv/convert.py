import os
import shutil
from bs4 import BeautifulSoup
from five import grok
from io import BytesIO
from os import path, walk, remove
from zipfile import ZipFile
from zope.component.hooks import getSite
from Products.CMFPlone.interfaces import IPloneSiteRoot
from collective.documentviewer.settings import GlobalSettings
from collective.documentviewer.convert import DUMP_FILENAME
from collective.documentviewer.convert import DocSplitSubProcess
from collective.documentviewer.utils import mkdir_p
from logging import getLogger


log = getLogger(__name__)

grok.templatedir('templates')


class DocconvDocSplitSubProcess(DocSplitSubProcess):
    """Customised to limit the number of pages"""

    def dump_images(self, filepath, output_dir, sizes, format, lang='eng', limit=20):
        # docsplit images pdf.pdf --size 700x,300x,50x
        # --format gif --output
        pages = self.get_num_pages(filepath)
        if pages < limit:
            limit = pages
        cmd = [self.binary, "images", filepath,
            '--language', lang,
            '--size', ','.join([str(s[1]) + 'x' for s in sizes]),
            '--format', format,
            '--rolling',
            '--output', output_dir,
            '--pages', '1-%s' % limit]
        if lang != 'eng':
            # cf https://github.com/documentcloud/docsplit/issues/72
            # the cleaning functions are only suited for english
            cmd.append('--no-clean')

        self._run_command(cmd)

        # now, move images to correctly named folders
        for name, size in sizes:
            dest = os.path.join(output_dir, name)
            if os.path.exists(dest):
                shutil.rmtree(dest)

            source = os.path.join(output_dir, '%ix' % size)
            shutil.move(source, dest)


try:
    docsplit = DocconvDocSplitSubProcess()
except IOError:
    log.exception("No docsplit installed. slc.docconv will not work.")
    docsplit = None


def get_file_locations(filename, content_type, gsettings):
    storage_dir = path.join(gsettings.storage_location, filename)
    if content_type == 'application/octetstream':
        filename_dump = path.join(
            gsettings.storage_location, '.'.join((filename, 'html')))
    else:
        filename_dump = path.join(
            gsettings.storage_location, filename)
        if filename_dump.endswith(filename):
            filename_dump = '.'.join([filename_dump, 'dat'])
    filename_pdf = path.join(storage_dir, 'converted.pdf')

    if not path.exists(storage_dir):
        mkdir_p(storage_dir)
    if path.exists(filename_dump):
        remove(filename_dump)

    return (storage_dir, filename_dump, filename_pdf)


def _dump_zipfile(payload, filename_dump, gsettings):
    # extract it
    stream = BytesIO(payload)
    fzip = ZipFile(stream)
    fzipfilelist = fzip.filelist
    html = [x.filename for x in fzipfilelist
            if x.filename.endswith('.html') or x.filename.endswith('.htm')]
    if not html:
        msg = 'No html file found in zip'
        raise TypeError(msg)
    fzip.extractall(gsettings.storage_location)
    source_path = path.join(gsettings.storage_location, html[0])
    shutil.move(source_path, filename_dump)
    fzip.close()
    stream.close()

    # make img src paths absolute
    htmlfile = open(filename_dump, 'r')
    soup = BeautifulSoup(htmlfile.read())
    htmlfile.close()
    for img in soup.find_all('img'):
        if not 'src' in img:
            continue
        img['src'] = path.join(gsettings.storage_location, img['src'])
    htmlfile = open(filename_dump, 'w')
    htmlfile.write(str(soup))
    htmlfile.close()
    return (html, fzipfilelist)


def _prepare_pdf(storage_dir, filename_dump, filename_pdf, content_type):
    if 'pdf' in content_type:
        shutil.move(filename_dump, filename_pdf)
    else:
        if path.exists(path.join(storage_dir, DUMP_FILENAME)):
            remove(path.join(storage_dir, DUMP_FILENAME))
        docsplit.convert_to_pdf(filename_dump, filename_dump, storage_dir)
        shutil.move(path.join(storage_dir, DUMP_FILENAME), filename_pdf)


def _build_zip(storage_dir):
    stream = BytesIO()
    zipped = ZipFile(stream, 'w')
    for entry in walk(storage_dir):
        relpath = path.relpath(entry[0], storage_dir)
        if not entry[0] == storage_dir:
            # if it's not the top dir we want to add it
            zipped.write(entry[0], relpath.encode('CP437'))
        # we always want to add the contained files
        for filename in entry[2]:
            relative = path.join(relpath, filename)
            zipped.write(path.join(entry[0], filename), relative)
    zipped.close()
    zipdata = stream.getvalue()
    stream.close()

    return zipdata


def _read_file(dirpath, filename):
    infile = open(path.join(dirpath, filename), 'r')
    filedata = infile.read()
    infile.close()
    return filedata


def file_num_or_name(filename):
    try:
        return int(filename.split('.')[0].split('_')[-1])
    except ValueError:
        return filename


def _collect_data(storage_dir):
    converted = {
        'pdfs': [],
        'thumbnails': [],
        'previews': [],
    }
    for (dirpath, dirnames, filenames) in walk(storage_dir):
        for filename in sorted(filenames, key=file_num_or_name):
            if filename.endswith('.pdf'):
                converted['pdfs'].append(_read_file(dirpath, filename))
            elif dirpath.endswith('small'):
                converted['thumbnails'].append(_read_file(dirpath, filename))
            elif dirpath.endswith('large'):
                converted['previews'].append(_read_file(dirpath, filename))
    return converted


def convert_filedata(filename, payload, content_type, gsettings=None, process_output=_build_zip):
    if not docsplit:
        msg = 'docsplit not found, check that docsplit is installed'
        raise IOError(msg)

    if gsettings is None:
        gsettings = GlobalSettings(getSite())

    fzipfilelist = []
    if '.' in filename:
        filename = '.'.join(filename.split('.')[:-1])
    (storage_dir, filename_dump, filename_pdf) = get_file_locations(
        filename, content_type, gsettings)

    # do we have a zip file?
    if content_type == 'application/octetstream':
        (html, fzipfilelist) = _dump_zipfile(payload, filename_dump, gsettings)
    else:
        fi = open(filename_dump, 'wb')
        fi.write(payload)
        fi.close()

    _prepare_pdf(storage_dir, filename_dump, filename_pdf, content_type)

    args = dict(
        sizes=(('large', gsettings.large_size),
               ('normal', gsettings.normal_size),
               ('small', gsettings.thumb_size)),
        ocr=gsettings.ocr,
        detect_text=gsettings.detect_text,
        format=gsettings.pdf_image_format,
        converttopdf=False,
        filename=filename,
        inputfilepath=filename_pdf)
    docsplit.convert(storage_dir, **args)

    output = process_output(storage_dir)

    # clean up
    shutil.rmtree(storage_dir)
    for ff in fzipfilelist:
        # html[0] has already been consumed by convert_to_pdf. The rest needs
        # to be cleaned up
        if not ff.filename == html[0]:
            remove(path.join(gsettings.storage_location, ff.filename))

    return output


def convert_to_zip(filename, payload, content_type, gsettings=None):
    zipdata = convert_filedata(
        filename, payload, content_type, gsettings=gsettings, process_output=_build_zip)
    return zipdata


def convert_to_raw(filename, payload, content_type, gsettings=None):
    rawdata = convert_filedata(
        filename, payload, content_type, gsettings=gsettings, process_output=_collect_data)
    return rawdata


class ConvertExternal(grok.View):
    grok.name('convert-external')
    grok.context(IPloneSiteRoot)
    grok.require('zope2.View')

    def update(self):
        self.gsettings = GlobalSettings(self.context)

    def render(self):
        filedata = self.request.get('filedata')
        if not filedata:
            self.request.RESPONSE.setStatus(415)
            msg = 'No filedata found'
            log.warn(msg)
            return msg

        filename_base = filedata.filename.decode('utf8')
        payload = filedata.read()
        content_type = filedata.headers.get('content-type')
        try:
            zipdata = convert_to_zip(
                filename_base, payload, content_type, gsettings=self.gsettings)
        except IOError as e:
            self.request.RESPONSE.setStatus(500)
            log.error(e)
            return str(e)
        except TypeError as e:
            self.request.RESPONSE.setStatus(415)
            log.warn(e)
            return str(e)

        response_filename = '.'.join((filename_base, u'zip')).encode('utf8')
        R = self.request.RESPONSE
        R.setHeader('content-type', 'application/zip')
        R.setHeader('content-disposition', 'inline; filename="%s"' % response_filename)
        R.setHeader('content-length', str(len(zipdata)))
        return zipdata


class ConvertUpload(grok.View):
    grok.name('convert-upload')
    grok.context(IPloneSiteRoot)
    grok.require('slc.docconv.convert')
    grok.template('convert')
