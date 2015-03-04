import os
import unittest2 as unittest
from ZPublisher.HTTPRequest import FileUpload
from cgi import FieldStorage
from io import BytesIO
from plone import api
from slc.docconv.testing import SLC_DOCCONV_INTEGRATION_TESTING
from zipfile import ZipFile


class TestConvert(unittest.TestCase):

    layer = SLC_DOCCONV_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.request = self.layer['request']

    def test_convert_empty(self):
        self.request.form = {}
        convert = api.content.get_view(
            context=self.portal,
            request=self.request,
            name='convert-external')
        convert()
        self.assertEqual(self.request.response.getStatus(), 415)

    def test_convert_file(self):
        in_file = open(os.path.join(os.path.dirname(__file__), 'test.odt'), 'r')
        env = {'REQUEST_METHOD': 'PUT'}
        headers = {'content-type': 'text/html',
                   'content-length': len(in_file.read()),
                   'content-disposition': 'attachment; filename=%s' % 'test.odt'}
        in_file.seek(0)
        fs = FieldStorage(fp=in_file, environ=env, headers=headers)
        f = FileUpload(fs)
        self.request.form = {
            'filedata': f,
        }
        convert = api.content.get_view(
            context=self.portal,
            request=self.request,
            name='convert-external')
        output = convert()
        stream = BytesIO(output)
        fzip = ZipFile(stream)

        pdfs = [x.filename for x in fzip.filelist
                if x.filename.endswith('.pdf')]
        self.assertGreaterEqual(len(pdfs), 1)
        self.assertGreaterEqual(len(fzip.read(pdfs[0])), 1)

        thumbs = [x.filename for x in fzip.filelist
                  if x.filename.startswith('small/')
                  and x.filename != 'small/']
        self.assertGreaterEqual(len(thumbs), 1)
        self.assertGreaterEqual(len(fzip.read(thumbs[0])), 1)

        previews = [x.filename for x in fzip.filelist
                    if x.filename.startswith('large/')
                    and x.filename != 'large/']
        self.assertGreaterEqual(len(previews), 1)
        self.assertGreaterEqual(len(fzip.read(previews[0])), 1)

        in_file.close()
