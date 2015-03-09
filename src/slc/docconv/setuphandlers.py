from collective.documentviewer.settings import GlobalSettings
from plone import api


def documentviewer_settings(context):
    if context.readDataFile('slc.docconv.txt') is None:
        return
    portal = api.portal.get()
    gsettings = GlobalSettings(portal)
    gsettings.storage_location = '/tmp'
