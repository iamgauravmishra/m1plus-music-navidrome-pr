#!/usr/bin/env python3
"""The translations of every text M1 Pod adds (docs/ui.md "Localisation").

The stock app translates through AWTK: a widget's `tr_text` is a key into strings/<lang>_<COUNTRY>.bin
(locale_info_tr 0x658db4, a binary search by strcmp; a key the table lacks comes back unchanged).
M1 Pod's texts use two kinds of key:

  * STOCK    a key the stock tables already carry with a good translation in every language (checked by
             test/pod/i18n.py against the shipped tables): used as it is.
  * TEXT     our own keys. The key IS the English text, so a missing table or entry shows English, which is
             also the text of en_US. tools/mod_strings.py adds these to all 16 tables.

Brand names stay as they are (M1 Pod, Tidal, Shanling inside a longer text). Locales: the language menu
reaches 13 tables (switch_language 0x4cca40: zh_CN is the default, then zh_HK en_US ja_JP ko_KR fr_FR ge_DE
sp_ES it_IT th_TH po_PL ru_RU uk_UK); de_DE, es_ES and pl_PL are 11-entry stubs of the CD ripper strings
that nothing loads: they get our keys as their twin's text (ge_DE, sp_ES, po_PL = German, Spanish, Polish).
The terms follow the stock tables where they are sound (library = 曲库 / Datenbank / librería ...,
artist = 歌手 / Künstler ...).
"""

LOCALES = ['en_US', 'zh_CN', 'zh_HK', 'ja_JP', 'ko_KR', 'fr_FR', 'ge_DE', 'sp_ES', 'it_IT', 'th_TH', 'po_PL', 'ru_RU', 'uk_UK']
TWINS = {'de_DE': 'ge_DE', 'es_ES': 'sp_ES', 'pl_PL': 'po_PL'}      # unreachable stub tables -> the table that holds their language
ALL_TABLES = sorted(LOCALES + list(TWINS))

# Stock keys used as they are: key -> the English text of en_US (the test compares it with the shipped table).
STOCK = {
    'cdrippersettings': 'Settings',
    'hr': 'Hi-Res',
    'sset_updatemusic': 'Update Library',
    'cdripper': 'CD Ripper',
    'album': 'Album',
}

_L = LOCALES[1:]    # the order of the translations below (English is the key)


def _t(key, *texts, **by):
    """key -> {locale: text}; texts are in _L order, `by` overrides or supplies single locales."""
    d = dict(zip(_L, texts)); d.update(by); d['en_US'] = key
    assert set(d) == set(LOCALES), (key, sorted(set(LOCALES) - set(d)))
    return key, d


#       zh_CN    zh_HK    ja_JP    ko_KR    fr_FR    ge_DE    sp_ES    it_IT    th_TH    po_PL    ru_RU    uk_UK
TEXT = dict([
    _t('Now Playing', '正在播放', '正在播放', '再生中', '지금 재생 중', 'En lecture', 'Jetzt läuft',
       'Reproduciendo', 'In riproduzione', 'กำลังเล่น', 'Teraz gra', 'Сейчас играет', 'Зараз грає'),
    _t('Cover Flow', '封面流', '封面流', 'カバーフロー', '커버 플로우', 'Cover Flow', 'Cover Flow',
       'Cover Flow', 'Cover Flow', 'Cover Flow', 'Cover Flow', 'Cover Flow', 'Cover Flow'),
    _t('Albums', '专辑', '專輯', 'アルバム', '앨범', 'Albums', 'Alben',
       'Álbumes', 'Album', 'อัลบั้ม', 'Albumy', 'Альбомы', 'Альбоми'),
    _t('Artists', '歌手', '歌手', 'アーティスト', '아티스트', 'Artistes', 'Künstler',
       'Artistas', 'Artisti', 'ศิลปิน', 'Wykonawcy', 'Исполнители', 'Виконавці'),
    _t('Songs', '歌曲', '歌曲', '曲', '노래', 'Titres', 'Titel',
       'Canciones', 'Brani', 'เพลง', 'Utwory', 'Песни', 'Пісні'),
    _t('Playlists', '歌单', '歌單', 'プレイリスト', '플레이리스트', 'Playlists', 'Playlists',
       'Listas', 'Playlist', 'เพลย์ลิสต์', 'Playlisty', 'Плейлисты', 'Плейлисти'),
    _t('Shuffle', '随机播放', '隨機播放', 'シャッフル', '임의 재생', 'Aléatoire', 'Zufall',
       'Aleatorio', 'Casuale', 'สุ่มเพลง', 'Losowo', 'Перемешать', 'Перемішати'),
    _t('Genres', '风格', '風格', 'ジャンル', '장르', 'Genres', 'Genres',
       'Géneros', 'Generi', 'ประเภท', 'Gatunki', 'Жанры', 'Жанри'),
    _t('Folders', '文件夹', '資料夾', 'フォルダ', '폴더', 'Dossiers', 'Ordner',
       'Carpetas', 'Cartelle', 'โฟลเดอร์', 'Foldery', 'Папки', 'Папки'),
    _t('Extras', '附加功能', '附加功能', 'エクストラ', '부가 기능', 'Extras', 'Extras',
       'Extras', 'Extra', 'เพิ่มเติม', 'Dodatki', 'Дополнительно', 'Додатково'),
    _t('Shuffle Songs', '随机播放歌曲', '隨機播放歌曲', '曲をシャッフル', '노래 임의 재생', 'Titres aléatoires', 'Titel mischen',
       'Canciones aleatorias', 'Brani casuali', 'สุ่มเพลง', 'Losuj utwory', 'Перемешать песни', 'Перемішати пісні'),
    _t('Shuffle Albums', '随机播放专辑', '隨機播放專輯', 'アルバムをシャッフル', '앨범 임의 재생', 'Albums aléatoires', 'Alben mischen',
       'Álbumes aleatorios', 'Album casuali', 'สุ่มอัลบั้ม', 'Losuj albumy', 'Перемешать альбомы', 'Перемішати альбоми'),
    _t('Shuffle Folders', '随机播放文件夹', '隨機播放資料夾', 'フォルダをシャッフル', '폴더 임의 재생', 'Dossiers aléatoires', 'Ordner mischen',
       'Carpetas aleatorias', 'Cartelle casuali', 'สุ่มโฟลเดอร์', 'Losuj foldery', 'Перемешать папки', 'Перемішати папки'),
    _t('Main Menu', '主菜单', '主選單', 'メインメニュー', '메인 메뉴', 'Menu principal', 'Hauptmenü',
       'Menú principal', 'Menu principale', 'เมนูหลัก', 'Menu główne', 'Главное меню', 'Головне меню'),
    _t('Start in M1 Pod', '启动进入 M1 Pod', '啟動進入 M1 Pod', '起動時に M1 Pod', '시작 시 M1 Pod', 'Démarrer sur M1 Pod', 'Start in M1 Pod',
       'Iniciar en M1 Pod', 'Avvia in M1 Pod', 'เริ่มที่ M1 Pod', 'Start w M1 Pod', 'Запуск в M1 Pod', 'Запуск у M1 Pod'),
    _t('Playback', '播放', '播放', '再生', '재생', 'Lecture', 'Wiedergabe',
       'Reproducción', 'Riproduzione', 'การเล่น', 'Odtwarzanie', 'Воспроизведение', 'Відтворення'),
    _t('System Settings', '系统设置', '系統設定', 'システム設定', '시스템 설정', 'Réglages système', 'Systemeinstellungen',
       'Ajustes del sistema', 'Impostazioni di sistema', 'การตั้งค่าระบบ', 'Ustawienia systemowe', 'Системные настройки', 'Системні налаштування'),
    _t('Shanling Home', '山灵主页', '山靈主頁', 'Shanling ホーム', 'Shanling 홈', 'Accueil Shanling', 'Shanling-Start',
       'Inicio Shanling', 'Home Shanling', 'หน้าหลัก Shanling', 'Ekran Shanling', 'Экран Shanling', 'Екран Shanling'),
    _t('Favorites', '我的最爱', '我的最愛', 'お気に入り', '즐겨찾기', 'Favoris', 'Favoriten',
       'Favoritos', 'Preferiti', 'รายการโปรด', 'Ulubione', 'Избранное', 'Вибране'),
    _t('Recently Added', '最近添加', '最近新增', '最近追加した曲', '최근 추가됨', 'Ajoutés récemment', 'Kürzlich hinzugefügt',
       'Añadidos recientemente', 'Aggiunti di recente', 'เพิ่มล่าสุด', 'Ostatnio dodane', 'Недавно добавленные', 'Нещодавно додані'),
    _t('Recently Played', '最近播放', '最近播放', '最近再生した曲', '최근 재생', 'Lus récemment', 'Zuletzt gespielt',
       'Reproducido hace poco', 'Riprodotti di recente', 'เล่นล่าสุด', 'Ostatnio odtwarzane', 'Недавно слушали', 'Нещодавно відтворені'),
    _t('Most Played', '经常播放', '經常播放', 'よく再生する曲', '자주 듣는 음악', 'Les plus écoutés', 'Meistgespielt',
       'Más reproducidas', 'Più riprodotti', 'เล่นบ่อยที่สุด', 'Najczęściej odtwarzane', 'Часто слушаемые', 'Часто відтворювані'),
    _t('Composers', '作曲者', '作曲者', '作曲者', '작곡가', 'Compositeurs', 'Komponisten',
       'Compositores', 'Compositori', 'นักแต่งเพลง', 'Kompozytorzy', 'Композиторы', 'Композитори'),
    _t('Album Artists', '专辑表演者', '專輯表演者', 'アルバムアーティスト', '앨범 아티스트', "Artistes de l'album", 'Albumkünstler',
       'Artistas del álbum', "Artisti dell'album", 'ศิลปินอัลบั้ม', 'Wykonawcy albumu', 'Исполнители альбома', 'Виконавці альбому'),
    _t('Play all', '全部播放', '全部播放', 'すべて再生', '모두 재생', 'Tout lire', 'Abspielen',
       'Reproducir', 'Riproduci', 'เล่นทั้งหมด', 'Odtwórz', 'Слушать', 'Відтворити'),
    _t('Cancel', '取消', '取消', 'キャンセル', '취소', 'Annuler', 'Abbrechen',
       'Cancelar', 'Annulla', 'ยกเลิก', 'Anuluj', 'Отмена', 'Скасувати'),
    _t('Update Local Music first', '请先更新曲库', '請先更新曲庫', '先にライブラリを更新', '먼저 라이브러리를 업데이트하세요',
       'Mettez la bibliothèque à jour', 'Datenbank zuerst aktualisieren', 'Actualiza primero la librería',
       'Aggiorna prima la libreria', 'อัพเดทรายการเพลงก่อน', 'Najpierw zaktualizuj bibliotekę', 'Сначала обновите библиотеку', 'Спочатку оновіть медіатеку'),
    _t('Not enough memory', '内存不足', '記憶體不足', 'メモリ不足', '메모리 부족', 'Mémoire insuffisante', 'Nicht genug Speicher',
       'Memoria insuficiente', 'Memoria insufficiente', 'หน่วยความจำไม่พอ', 'Za mało pamięci', 'Недостаточно памяти', "Недостатньо пам'яті"),
    _t('Storage unavailable', '存储不可用', '儲存空間無法使用', 'ストレージを利用できません', '저장 장치를 사용할 수 없음', 'Stockage indisponible', 'Speicher nicht verfügbar',
       'Almacenamiento no disponible', 'Archivio non disponibile', 'ไม่พบที่เก็บข้อมูล', 'Pamięć niedostępna', 'Хранилище недоступно', 'Сховище недоступне'),
    _t('Too many songs to shuffle', '歌曲太多，无法随机播放', '歌曲太多，無法隨機播放', '曲が多すぎます', '노래가 너무 많음',
       'Trop de titres à mélanger', 'Zu viele Titel zum Mischen', 'Demasiadas canciones', 'Troppi brani da mescolare',
       'เพลงมากเกินไปสำหรับสุ่ม', 'Za dużo utworów do losowania', 'Слишком много песен', 'Забагато пісень'),
    _t('All albums', '所有专辑', '所有專輯', 'すべてのアルバム', '모든 앨범', 'Tous les albums', 'Alle Alben',
       'Todos los álbumes', 'Tutti gli album', 'อัลบั้มทั้งหมด', 'Wszystkie albumy', 'Все альбомы', 'Усі альбоми'),
    _t('Preparing covers...', '正在准备封面...', '正在準備封面...', 'カバーを準備中...', '커버 준비 중...', 'Création des pochettes...', 'Cover werden erstellt...',
       'Preparando carátulas...', 'Preparazione copertine...', 'กำลังเตรียมปก...', 'Przygotowanie okładek...', 'Подготовка обложек...', 'Готуємо обкладинки...'),
    _t('Library too large', '曲库太大', '曲庫太大', 'ライブラリが大きすぎます', '라이브러리가 너무 큼', 'Bibliothèque trop volumineuse', 'Datenbank zu groß',
       'Librería demasiado grande', 'Libreria troppo grande', 'รายการเพลงมากเกินไป', 'Biblioteka jest za duża', 'Библиотека слишком велика', 'Медіатека завелика'),
    _t('No albums', '没有专辑', '沒有專輯', 'アルバムがありません', '앨범 없음', 'Aucun album', 'Keine Alben',
       'Sin álbumes', 'Nessun album', 'ไม่มีอัลบั้ม', 'Brak albumów', 'Нет альбомов', 'Немає альбомів'),
    # the Settings > Cover Flow sub-page (landscape switch; sort order, valued Artist or Album: "Album" is the stock key 'album')
    _t('Landscape', '横屏', '橫向', '横向き', '가로 모드', 'Paysage', 'Querformat',
       'Horizontal', 'Orizzontale', 'แนวนอน', 'Poziomo', 'Горизонтально', 'Горизонтально'),
    _t('Sort', '排序', '排序', '並べ替え', '정렬', 'Trier', 'Sortieren',
       'Ordenar', 'Ordina', 'เรียงลำดับ', 'Sortuj', 'Сортировка', 'Сортування'),
    _t('Artist', '歌手', '歌手', 'アーティスト', '아티스트', 'Artiste', 'Künstler',
       'Artista', 'Artista', 'ศิลปิน', 'Wykonawca', 'Исполнитель', 'Виконавець'),
    # the track count of the album page's header: the payload chooses the key by n == 1 and puts the number where %d is;
    # languages with more than two plural forms (pl, ru, uk) use a label that needs none ("Tracks: 12")
    _t('%d track', '%d 首歌曲', '%d 首歌曲', '%d 曲', '%d곡', '%d titre', '%d Titel',
       '%d canción', '%d brano', '%d เพลง', 'Utwory: %d', 'Песен: %d', 'Пісень: %d'),
    _t('%d tracks', '%d 首歌曲', '%d 首歌曲', '%d 曲', '%d곡', '%d titres', '%d Titel',
       '%d canciones', '%d brani', '%d เพลง', 'Utwory: %d', 'Песен: %d', 'Пісень: %d'),
])

KEYS = sorted(TEXT)


def english(key):
    """The English text a key stands for (our keys are their own English; stock keys come from STOCK)."""
    return TEXT[key]['en_US'] if key in TEXT else STOCK[key]


BRANDS = ('M1 Pod', 'Tidal')     # shown as they are, no key


def key_for(english):
    """The tr_text key of an English text we show: itself (our keys), the stock key whose en_US text it is, or None
    for a brand name, which stays a plain text."""
    if english in TEXT: return english
    for k, v in STOCK.items():
        if v == english: return k
    assert english in BRANDS, f'no translation key for {english!r}'
    return None


def text_prop(english):
    """The (property, value) pair an asset widget shows `english` with: tr_text with its key, or text for a brand."""
    key = key_for(english)
    return ('tr_text', key) if key else ('text', english)


def shown_english(w):
    """The English text of an asset widget (tr_text or text)."""
    k = w.get('tr_text')
    return english(k) if k is not None else w.get('text')


def table_for(locale):
    """The language a table file holds: a stub table holds its twin's."""
    return TWINS.get(locale, locale)


def tr(locale, key, stock=None):
    """What a widget with tr_text `key` shows in `locale`. Our keys: the TEXT entry. A stock key: the entry of `stock`
    (a {locale: {key: text}} read from the shipped tables), else the key itself, as locale_info_tr returns it."""
    if key in TEXT: return TEXT[key][table_for(locale)]
    if stock is not None: return stock.get(locale, {}).get(key, key)
    return key


def add_to_tables(tables):
    """tables: {locale: [(key, value), ...]} (awtk_strings.items) -> the same with our keys added, sorted for the
    binary search. Refuses a table that already has one of our keys."""
    out = {}
    for loc, items in tables.items():
        have = {k for k, _ in items}
        assert not have & set(TEXT), f'{loc}: already has {sorted(have & set(TEXT))}'
        out[loc] = sorted(items + [(k, TEXT[k][table_for(loc)]) for k in TEXT], key=lambda kv: kv[0].encode())
    return out
