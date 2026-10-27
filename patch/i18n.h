/* M1+ Pod texts in the language the player is set to: the stock translation (docs/architecture.md
 * "Localisation"). A key is looked up in the current strings/<lang>_<COUNTRY>.bin by locale_info_tr
 * (0x658db4, a binary search); a key the table lacks (or no table at all) comes back unchanged, and our
 * keys are their English text, so the worst case is English. widget_set_tr_text (0x66f994) keeps the key
 * on the widget, so the window manager's locale-changed handler (0x6772dc) re-translates it while the
 * page is open. Texts that are composed (a count, a progress) are built from TR() at the moment they are
 * set. Keys and translations: tools/pod_i18n.py, added to the tables by tools/mod_strings.py. */
#pragma once

#define TR(key) locale_info_tr(locale_info(), (key))
