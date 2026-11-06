"""Podcast Region: the Apple Podcasts storefronts the picker offers, and how Automatic infers one (patch/pcregion.c, docs/modules/podcasts.md "Region").

The region drives the directory search (`&country=`) and the Discover charts (`.../api/v2/<cc>/...`). The saved choice is /mnt/data/m1plus/podcast-region: the two letter code and a line feed;
no file (or anything else) is Automatic. Automatic takes the UI language's country where one language is one country, else the Settings time zone's, else the United States.
"""
import timezones

# (code, English name) in the picker's order: by name ("UK", not United Kingdom: the Settings row has no glyph and its label and value share the room, test/pod/i18n.py). The names are English in every language (no localised table of country names exists in the repo or in the stock tables).
REGIONS = (
    ('AR', 'Argentina'), ('AU', 'Australia'), ('AT', 'Austria'), ('BE', 'Belgium'), ('BR', 'Brazil'), ('CA', 'Canada'), ('CN', 'China'), ('DK', 'Denmark'),
    ('FI', 'Finland'), ('FR', 'France'), ('DE', 'Germany'), ('HK', 'Hong Kong'), ('IN', 'India'), ('IE', 'Ireland'), ('IT', 'Italy'), ('JP', 'Japan'),
    ('MX', 'Mexico'), ('NL', 'Netherlands'), ('NZ', 'New Zealand'), ('NO', 'Norway'), ('PL', 'Poland'), ('PT', 'Portugal'), ('RU', 'Russia'), ('SG', 'Singapore'),
    ('ZA', 'South Africa'), ('KR', 'South Korea'), ('ES', 'Spain'), ('SE', 'Sweden'), ('CH', 'Switzerland'), ('TW', 'Taiwan'), ('TH', 'Thailand'), ('GB', 'UK'), ('UA', 'Ukraine'),
    ('US', 'United States'),
)
CODES = tuple(c for c, _ in REGIONS)
NAMES = tuple(n for _, n in REGIONS)
assert list(NAMES) == sorted(NAMES) and len(set(CODES)) == len(CODES) == 34
DEFAULT = 'US'
FILE = '/mnt/data/m1plus/podcast-region'

# The UI language (locale_info's language token, then its country) -> the storefront; en and sp (Spanish) are not one country: the time zone decides.
LANGUAGES = (('ja', None, 'JP'), ('ko', None, 'KR'), ('zh', 'HK', 'HK'), ('zh', 'TW', 'TW'), ('zh', None, 'CN'), ('ge', None, 'DE'), ('fr', None, 'FR'),
             ('it', None, 'IT'), ('po', None, 'PL'), ('th', None, 'TH'), ('ru', None, 'RU'), ('uk', None, 'UA'))
# The Settings time zone's index (tools/timezones.py) -> the storefront, for the zones that name a place with one (others, and the stock default 22, Shanghai, are not a choice).
ZONES = {2: 'US', 3: 'US', 4: 'US', 5: 'US', 6: 'MX', 7: 'US', 8: 'CA', 9: 'CA', 10: 'AR', 12: 'GB', 13: 'NL', 21: 'TH', 23: 'JP', 24: 'AU', 25: 'AU',
         32: 'AU', 33: 'AU', 35: 'NZ', 38: 'US', 39: 'US', 40: 'IN', 41: 'AU', 42: 'NZ'}
assert all(0 <= i < timezones.COUNT and c in CODES for i, c in ZONES.items()) and timezones.DEFAULT not in ZONES
ZONE_TABLE = tuple(ZONES.get(i, '') for i in range(timezones.COUNT))


def infer(language, country, zone):
    """The storefront Automatic gives: the language's, for en / sp the zone's (not the stock default), else US."""
    for lang, cc, region in LANGUAGES:
        if language == lang and (cc is None or cc == country): return region
    if language in ('en', 'sp') and zone != timezones.DEFAULT: return ZONES.get(zone, DEFAULT)
    return DEFAULT


def index_of(code):
    """The picker row of a saved code: 1.. (0 is Automatic); 0 for a code that is not offered."""
    return CODES.index(code) + 1 if code in CODES else 0
