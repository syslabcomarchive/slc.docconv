from AccessControl.SecurityInfo import ModuleSecurityInfo
from Products.CMFCore.permissions import setDefaultRoles

security = ModuleSecurityInfo('slc.docconv')
security.declarePublic('Convert')
Convert = 'slc.docconv: Convert'
setDefaultRoles(Convert, ('Manager'))
