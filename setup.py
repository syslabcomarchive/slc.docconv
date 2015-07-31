from setuptools import setup, find_packages
import os

version = '1.3'

long_description = (
    open('README.txt').read()
    + '\n' +
    'Contributors\n'
    '============\n'
    + '\n' +
    open('CONTRIBUTORS.txt').read()
    + '\n' +
    open('CHANGES.txt').read()
    + '\n')

setup(name='slc.docconv',
      version=version,
      description="Add-on for collective.documentviewer that allows web service like conversion",
      long_description=long_description,
      # Get more strings from
      # http://pypi.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        "Programming Language :: Python",
        ],
      keywords='collective documentviewer conversion pdf office',
      author='Syslab.com GmbH',
      author_email='info@syslab.com',
      url='http://syslab.com/',
      license='gpl',
      packages=find_packages('src'),
      package_dir = {'': 'src'},
      namespace_packages=['slc', ],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          # -*- Extra requirements: -*-
          'collective.documentviewer',
          'five.grok',
          'beautifulsoup4',
      ],
      extras_require={
          'test': [
              'plone.app.testing',
              'plone.api',
          ]
      },
      entry_points="""
      # -*- Entry points: -*-
      [z3c.autoinclude.plugin]
      target = plone
      """,
      )
