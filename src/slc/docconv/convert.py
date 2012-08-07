import shutil
from bs4 import BeautifulSoup
from five import grok
from os import path, walk, remove
from zipfile import ZipFile
from tempfile import TemporaryFile
from Products.CMFPlone.interfaces import IPloneSiteRoot
from collective.documentviewer.settings import GlobalSettings
from collective.documentviewer.convert import docsplit, DUMP_FILENAME
from collective.documentviewer.utils import mkdir_p

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
            return 'No filedata found'
        if not docsplit:
            self.request.RESPONSE.setStatus(500)
            return 'docsplit not found, check that docsplit is installed'

        fzipfilelist = []
        filename_base = '.'.join(filedata.filename.decode('utf8').split('.')[:-1])
        storage_dir = path.join(self.gsettings.storage_location, filename_base)
        if filedata.headers.get('content-type') == 'application/octetstream':
            filename_dump = path.join(self.gsettings.storage_location, '.'.join((filename_base, 'html')))
        else:
            filename_dump = path.join(self.gsettings.storage_location, filedata.filename.decode('utf8'))
        filename_pdf = path.join(storage_dir, 'coverted.pdf') #'.'.join((filename_base, 'pdf')))

        if not path.exists(storage_dir):
            mkdir_p(storage_dir)
        if path.exists(filename_dump):
            remove(filename_dump)
        # do we have a zip file?
        if filedata.headers.get('content-type') == 'application/octetstream':
            # extract it
            ff = TemporaryFile()
            ff.write(filedata.read())
            fzip = ZipFile(ff)
            fzipfilelist = fzip.filelist
            html = [x.filename for x in fzipfilelist if x.filename.endswith('.html') or x.filename.endswith('.htm')]
            if not html:
                self.request.RESPONSE.setStatus(415)
                return 'No html file found in zip'
            fzip.extractall(self.gsettings.storage_location)
            shutil.move(path.join(self.gsettings.storage_location, html[0]), filename_dump)
            fzip.close()
            ff.close()

            # make img src paths absolute
            htmlfile = open(filename_dump, 'r')
            soup = BeautifulSoup(htmlfile.read())
            htmlfile.close()
            for img in soup.find_all('img'):
                img['src'] = path.join(self.gsettings.storage_location, img['src'])
            htmlfile = open(filename_dump, 'w')
            htmlfile.write(str(soup))
            htmlfile.close()

        else:
            fi = open(filename_dump, 'wb')
            fi.write(filedata.read())
            fi.close()

        #if filedata.filename.decode('utf8').lower().endswith('pdf'):
        if 'pdf' in filedata.headers.get('content-type'):
            shutil.move(filename_dump, filename_pdf)
        else:
            if path.exists(path.join(storage_dir, DUMP_FILENAME)):
                remove(path.join(storage_dir, DUMP_FILENAME))
            docsplit.convert_to_pdf(filename_dump, filedata.filename.decode('utf8'), storage_dir)
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
        num_pages = docsplit.convert(storage_dir, **args)

        filename_zip = path.join(self.gsettings.storage_location, '.'.join((filename_base, 'zip')))
        zipped = ZipFile(filename_zip, 'w')
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
        zipfd = open(filename_zip, 'r')
        zipdata = zipfd.read()
        zipfd.close()
        remove(filename_zip)
        shutil.rmtree(storage_dir)
        for ff in fzipfilelist:
            if not ff.filename == html[0]: # this one has already been consumed by convert_to_pdf
                remove(path.join(self.gsettings.storage_location, ff.filename))

        R = self.request.RESPONSE
        R.setHeader('content-type', 'application/zip')
        R.setHeader('content-disposition', 'inline; filename="%s"' % '.'.join((filename_base, u'zip')).encode('utf8'))
        R.setHeader('content-length', str(len(zipdata)))
        return zipdata
