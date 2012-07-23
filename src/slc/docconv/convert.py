import shutil
from five import grok
from os import path, listdir, walk
from zipfile import ZipFile
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
            return 'No filedata found'
        filename_base = '.'.join(filedata.filename.split('.')[:-1])
        storage_dir = path.join(self.gsettings.storage_location, filename_base)
        filename_dump = path.join(self.gsettings.storage_location, filedata.filename)
        filename_pdf = path.join(storage_dir, '.'.join((filename_base, 'pdf')))

        if not path.exists(storage_dir):
            mkdir_p(storage_dir)
        fi = open(filename_dump, 'wb')
        fi.write(filedata.read())
        fi.close()

        docsplit.convert_to_pdf(filename_dump, filedata.filename, storage_dir)
        shutil.move(path.join(storage_dir, DUMP_FILENAME), filename_pdf)

        args = dict(sizes=(('large', self.gsettings.large_size),
                           ('normal', self.gsettings.normal_size),
                           ('small', self.gsettings.thumb_size)),
                ocr=self.gsettings.ocr,
                detect_text=self.gsettings.detect_text,
                format=self.gsettings.pdf_image_format,
                converttopdf=False,
                filename=filedata.filename,
                inputfilepath=filename_pdf)
        num_pages = docsplit.convert(storage_dir, **args)

        filename_zip = path.join(self.gsettings.storage_location, '.'.join((filename_base, 'zip')))
        zipped = ZipFile(filename_zip, 'w')
        for entry in walk(storage_dir):
            relpath = path.relpath(entry[0], storage_dir)
            if not entry[0] == storage_dir:
                # if it's not the top dir we want to add it
                zipped.write(entry[0], relpath)
            # we always want to add the contained files
            for filename in entry[2]:
                relative = path.join(relpath, filename)
                zipped.write(path.join(entry[0], filename), relative)
        zipped.close()
        zipfd = open(filename_zip, 'r')
        zipdata = zipfd.read()

        R = self.request.RESPONSE
        R.setHeader('content-type', 'application/zip')
        R.setHeader('content-disposition', 'inline; filename="%s"' % '.'.join((filename_base, 'zip')))
        R.setHeader('content-length', str(len(zipdata)))
        return zipdata
