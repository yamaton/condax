#!/usr/bin/env xonsh
$PROJECT = 'condax'
$ACTIVITIES = [
	'version_bump',
	'changelog',
	'tag',
	'pypi',
	'push_tag',
	# 'ghrelease'
]

$GITHUB_ORG = 'mariusvniekerk'
$GITHUB_REPO = 'condax'

$VERSION_BUMP_PATTERNS = [
   # These note where/how to find the version numbers
   ('pyproject.toml', 'version\s*=.*', 'version = "$VERSION"'),
]

$CHANGELOG_FILENAME = 'docs/changelog.md'
$CHANGELOG_TEMPLATE = 'TEMPLATE.md'
$CHANGELOG_HEADER = '''
# $RELEASE_DATE $VERSION:

'''
