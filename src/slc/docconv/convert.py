import os
import shutil
from bs4 import BeautifulSoup
from five import grok
from io import BytesIO
from os import path, walk, remove
from zipfile import ZipFile
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
        if not docsplit:
            self.request.RESPONSE.setStatus(500)
            msg = 'docsplit not found, check that docsplit is installed'
            log.error(msg)
            return msg

        fzipfilelist = []
        filename_base = filedata.filename.decode('utf8')
        if '.' in filename_base:
            filename_base = '.'.join(filename_base.split('.')[:-1])
        storage_dir = path.join(self.gsettings.storage_location, filename_base)
        if filedata.headers.get('content-type') == 'application/octetstream':
            filename_dump = path.join(self.gsettings.storage_location, '.'.join((filename_base, 'html')))
        else:
            filename_dump = path.join(self.gsettings.storage_location, filedata.filename.decode('utf8'))
            if filename_dump.endswith(filename_base):
                filename_dump = '.'.join([filename_dump, 'dat'])
        filename_pdf = path.join(storage_dir, 'converted.pdf') #'.'.join((filename_base, 'pdf')))

        if not path.exists(storage_dir):
            mkdir_p(storage_dir)
        if path.exists(filename_dump):
            remove(filename_dump)
        # do we have a zip file?
        if filedata.headers.get('content-type') == 'application/octetstream':
            # extract it
            stream = BytesIO(filedata.read())
            fzip = ZipFile(stream)
            fzipfilelist = fzip.filelist
            html = [x.filename for x in fzipfilelist if x.filename.endswith('.html') or x.filename.endswith('.htm')]
            if not html:
                self.request.RESPONSE.setStatus(415)
                msg = 'No html file found in zip'
                log.warn(msg)
                return msg
            fzip.extractall(self.gsettings.storage_location)
            shutil.move(path.join(self.gsettings.storage_location, html[0]), filename_dump)
            fzip.close()
            stream.close()

            # make img src paths absolute
            htmlfile = open(filename_dump, 'r')
            soup = BeautifulSoup(htmlfile.read())
            htmlfile.close()
            for img in soup.find_all('img'):
                if not img.has_key('src'):
                    continue
                img['src'] = path.join(self.gsettings.storage_location, img['src'])
            htmlfile = open(filename_dump, 'w')
            htmlfile.write(str(soup))
            htmlfile.close()

        else:
            fi = open(filename_dump, 'wb')
            fi.write(filedata.read())
            fi.close()

        if 'pdf' in filedata.headers.get('content-type'):
            shutil.move(filename_dump, filename_pdf)
        else:
            if path.exists(path.join(storage_dir, DUMP_FILENAME)):
                remove(path.join(storage_dir, DUMP_FILENAME))
            docsplit.convert_to_pdf(filename_dump, filename_dump, storage_dir)
            shutil.move(path.join(storage_dir, DUMP_FILENAME), filename_pdf)

        args = dict(sizes=(('large', self.gsettings.large_size),
                           ('normal', self.gsettings.normal_size),
                           ('small', self.gsettings.thumb_size)),
                ocr=self.gsettings.ocr,
                detect_text=self.gsettings.detect_text,
                format=self.gsettings.pdf_image_format,
                converttopdf=False,
                filename=filedata.filename.decode('utf8'),
                inputfilepath=filename_pdf)
        docsplit.convert(storage_dir, **args)

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
        shutil.rmtree(storage_dir)
        for ff in fzipfilelist:
            if not ff.filename == html[0]: # this one has already been consumed by convert_to_pdf
                remove(path.join(self.gsettings.storage_location, ff.filename))

        R = self.request.RESPONSE
        R.setHeader('content-type', 'application/zip')
        R.setHeader('content-disposition', 'inline; filename="%s"' % '.'.join((filename_base, u'zip')).encode('utf8'))
        R.setHeader('content-length', str(len(zipdata)))
        return zipdata


class ConvertUpload(grok.View):
    grok.name('convert-upload')
    grok.context(IPloneSiteRoot)
    grok.require('slc.docconv.convert')
    grok.template('convert')
