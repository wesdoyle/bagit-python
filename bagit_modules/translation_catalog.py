import gettext

from bagit_modules.io import find_locale_dir

TRANSLATION_CATALOG = gettext.translation("bagit-python", localedir=find_locale_dir(), fallback=True)
_ = TRANSLATION_CATALOG.gettext
