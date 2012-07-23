from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import IntegrationTesting
from plone.app.testing import FunctionalTesting
from plone.app.testing import applyProfile

from zope.configuration import xmlconfig

class SlcDocconv(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE, )

    def setUpZope(self, app, configurationContext):
        # Load ZCML for this package
        import slc.docconv
        xmlconfig.file('configure.zcml',
                       slc.docconv,
                       context=configurationContext)


    def setUpPloneSite(self, portal):
        pass

SLC_DOCCONV_FIXTURE = SlcDocconv()
SLC_DOCCONV_INTEGRATION_TESTING = \
    IntegrationTesting(bases=(SLC_DOCCONV_FIXTURE, ),
                       name="SlcDocconv:Integration")