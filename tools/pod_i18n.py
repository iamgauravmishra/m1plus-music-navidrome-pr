#!/usr/bin/env python3
"""The translations of every text M1+ Music adds (docs/ui.md "Localisation").

The stock app translates through AWTK: a widget's `tr_text` is a key into strings/<lang>_<COUNTRY>.bin
(locale_info_tr 0x658db4, a binary search by strcmp; a key the table lacks comes back unchanged).
M1+ Music's texts use two kinds of key:

  * STOCK    a key the stock tables already carry with a good translation in every language (checked by
             test/pod/i18n.py against the shipped tables): used as it is.
  * TEXT     our own keys. The key IS the English text, so a missing table or entry shows English, which is
             also the text of en_US. tools/mod_strings.py adds these to all 16 tables.

Brand names stay as they are (M1+ Music, Tidal, Shanling inside a longer text). Locales: the language menu
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
    'cdrippersettings': 'Settings',   # the Pod's Settings row and level title (patch/ipod.c)
    'local_allsong': 'All Songs',     # the first row of an artist's album list and the title of its songs (patch/ipod.c); the stock All Songs, translated in every table
    'hr': 'Hi-Res',
    'sset_updatemusic': 'Update Library',
    'cdripper': 'CD Ripper',
    'album': 'Album',
    'playlist_create': 'New playlist',    # the Playlists page's menu: the stock Playlists page's own row texts
    'playlist_import': 'Import playlist',
    'playlist_export': 'Export playlist',
    'msg_playlistfull': 'Playlist Is Full',        # the message boxes of a New playlist that cannot be made (the stock create handler's)
    'msg_playlistexist': 'Playlist Already Exists',
    'msg_addplaylistsuccess': 'Added To Playlist',   # the Daily Mix page's Add disc and the stock playlist picker (@0x53d51c) after a successful add
    'sort_alphabet': 'Alphabetical',           # the Songs page's sort card: the stock sort dialog's five labels, in sort_flag order (patch/songs.c)
    'sort_filename': 'File name',
    'sort_format': 'File format',
    'sort_time_desc': 'Time added (descending)',
    'sort_time_asc': 'Time added (ascending)',
    'msg_delsong': 'Delete Song?',             # its confirm dialog and the stock message boxes it shows
    'msg_delsongfailed': 'Failed To Delete Song',
    'msg_delsongsuccess': 'Song Deleted',
    'msg_addfailed': 'Adding Failed',
    'msg_delplaylist': 'Delete Playlist?',     # the Playlists page's select mode: the stock delete handler's confirm dialog and message boxes (@0x53dbcc)
    'msg_delplaylistfailed': 'Failed To Delete Playlist',
    'msg_delplaylistsuccess': 'Playlist Deleted',
}

_L = LOCALES[1:]    # the order of the translations below (English is the key)


def _t(key, *texts, **by):
    """key -> {locale: text}; texts are in _L order, `by` overrides or supplies single locales."""
    d = dict(zip(_L, texts)); d.update(by); d['en_US'] = key
    assert set(d) == set(LOCALES), (key, sorted(set(LOCALES) - set(d)))
    return key, d


#       zh_CN    zh_HK    ja_JP    ko_KR    fr_FR    ge_DE    sp_ES    it_IT    th_TH    po_PL    ru_RU    uk_UK
TEXT = dict([
    _t('Appearance', '外观', '外觀', '外観', '화면 모드', 'Apparence', 'Darstellung',
       'Apariencia', 'Aspetto', 'รูปแบบหน้าจอ', 'Wygląd', 'Оформление', 'Вигляд'),
    _t('Light', '浅色', '淺色', 'ライト', '밝게', 'Clair', 'Hell',
       'Claro', 'Chiaro', 'สว่าง', 'Jasny', 'Светлая', 'Світла'),
    _t('Dark', '深色', '深色', 'ダーク', '어둡게', 'Sombre', 'Dunkel',
       'Oscuro', 'Scuro', 'มืด', 'Ciemny', 'Тёмная', 'Темна'),
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
    _t('Home Screen', '主屏幕', '主畫面', 'ホーム画面', '홈 화면', "Écran d'accueil", 'Startbildschirm',
       'Pantalla de inicio', 'Schermata Home', 'หน้าจอหลัก', 'Ekran główny', 'Главный экран', 'Головний екран'),
    _t('Boot to M1+ Music', '开机进入 M1+ Music', '開機進入 M1+ Music', '起動時に M1+ Music', '부팅 시 M1+ Music', 'Démarrer M1+ Music', 'Start mit M1+ Music',
       'Iniciar en M1+ Music', 'Avvio in M1+ Music', 'บูตเข้า M1+ Music', 'Start w M1+ Music', 'Запуск в M1+ Music', 'Запуск у M1+ Music'),
    _t('Customize', '自定义', '自訂', 'カスタマイズ', '사용자 지정', 'Personnaliser', 'Anpassen',
       'Personalizar', 'Personalizza', 'ปรับแต่ง', 'Dostosuj', 'Настройка', 'Персоналізація'),
    _t('Developer', '开发者', '開發者', '開発者向け', '개발자', 'Développeur', 'Entwickler',
       'Desarrollador', 'Sviluppatore', 'นักพัฒนา', 'Programista', 'Разработчик', 'Розробник'),
    _t('Playback', '播放', '播放', '再生', '재생', 'Lecture', 'Wiedergabe',
       'Reproducción', 'Riproduzione', 'การเล่น', 'Odtwarzanie', 'Воспроизведение', 'Відтворення'),
    _t('System Settings', '系统设置', '系統設定', 'システム設定', '시스템 설정', 'Réglages système', 'Systemeinstellungen',
       'Ajustes del sistema', 'Impostazioni di sistema', 'การตั้งค่าระบบ', 'Ustawienia systemowe', 'Системные настройки', 'Налаштування системи'),
    _t('Shanling Home', '山灵主页', '山靈主頁', 'Shanling ホーム', 'Shanling 홈', 'Accueil Shanling', 'Shanling-Start',
       'Inicio Shanling', 'Home Shanling', 'หน้าหลัก Shanling', 'Ekran Shanling', 'Экран Shanling', 'Екран Shanling'),
    _t('Favorites', '我的最爱', '我的最愛', 'お気に入り', '즐겨찾기', 'Favoris', 'Favoriten',
       'Favoritos', 'Preferiti', 'รายการโปรด', 'Ulubione', 'Избранное', 'Вибране'),
    _t('Recently Added', '最近添加', '最近新增', '最近追加した曲', '최근 추가됨', 'Ajoutés récemment', 'Kürzlich hinzugefügt',
       'Añadidos recientemente', 'Aggiunti di recente', 'เพิ่มล่าสุด', 'Ostatnio dodane', 'Недавно добавленные', 'Нещодавно додані'),
    _t('Recently Played', '最近播放', '最近播放', '最近再生した曲', '최근 재생', 'Lus récemment', 'Zuletzt gespielt',
       'Reproducido hace poco', 'Riprodotti di recente', 'เล่นล่าสุด', 'Ostatnio odtwarzane', 'Недавно слушали', 'Нещодавно відтворені'),
    # Customize > Home Screen > the Recently Played shelf's switch (patch/recent.c). Its own wording: the menu item's text above is too
    # wide for the switch row in Spanish and Ukrainian, and the shelf shows albums
    _t('Recent Albums', '最近专辑', '最近專輯', '最近のアルバム', '최근 앨범', 'Albums récents', 'Letzte Alben',
       'Álbumes recientes', 'Album recenti', 'อัลบั้มล่าสุด', 'Ostatnie albumy', 'Недавние альбомы', 'Нещодавні альбоми'),
    _t('Most Played','经常播放', '經常播放', 'よく再生する曲', '자주 듣는 음악', 'Les plus écoutés', 'Meistgespielt',
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
    _t('No artists', '没有艺术家', '沒有藝術家', 'アーティストがありません', '아티스트 없음', 'Aucun artiste', 'Keine Künstler',
       'Sin artistas', 'Nessun artista', 'ไม่มีศิลปิน', 'Brak wykonawców', 'Нет исполнителей', 'Немає виконавців'),
    _t('Music', '音乐', '音樂', 'ミュージック', '음악', 'Musique', 'Musik',
       'Música', 'Musica', 'เพลง', 'Muzyka', 'Музыка', 'Музика'),
    # the Settings > Cover Flow sub-page (landscape switch; sort order, valued Artist or Album: "Album" is the stock key 'album')
    _t('Landscape', '横屏', '橫向', '横向き', '가로 모드', 'Paysage', 'Querformat',
       'Horizontal', 'Orizzontale', 'แนวนอน', 'Poziomo', 'Горизонтально', 'Горизонтально'),
    _t('Sort', '排序', '排序', '並べ替え', '정렬', 'Trier', 'Sortieren',
       'Ordenar', 'Ordina', 'เรียงลำดับ', 'Sortuj', 'Сортировка', 'Сортування'),
    _t('Artist', '歌手', '歌手', 'アーティスト', '아티스트', 'Artiste', 'Künstler',
       'Artista', 'Artista', 'ศิลปิน', 'Wykonawca', 'Исполнитель', 'Виконавець'),
    # Settings > Cover Flow > Rebuild Covers: the row, and the message of the stock confirm dialog (a centred white 20 px label
    # that wraps in 260 x 80 px: at most three lines, test/pod/i18n.py)
    _t('Rebuild Covers', '重建封面', '重建封面', 'カバーを再作成', '커버 다시 만들기', 'Recréer les pochettes', 'Cover neu erstellen',
       'Recrear carátulas', 'Ricrea copertine', 'สร้างปกใหม่', 'Odbuduj okładki', 'Пересоздать обложки', 'Оновити обкладинки'),
    _t('Rebuild all covers? This may take a few minutes.', '重建所有封面？这可能需要几分钟。', '重建所有封面？這可能需要幾分鐘。',
       'すべてのカバーを再作成しますか？数分かかる場合があります。', '모든 커버를 다시 만들까요? 몇 분 걸릴 수 있습니다.',
       'Recréer toutes les pochettes ? Cela peut prendre quelques minutes.', 'Alle Cover neu erstellen? Das kann einige Minuten dauern.',
       '¿Recrear todas las carátulas? Puede tardar unos minutos.', 'Ricreare tutte le copertine? Potrebbe richiedere alcuni minuti.',
       'สร้างปกทั้งหมดใหม่หรือไม่ อาจใช้เวลาสองสามนาที', 'Odbudować wszystkie okładki? Może to potrwać kilka minut.',
       'Пересоздать все обложки? Это может занять несколько минут.', 'Оновити всі обкладинки? Це може тривати кілька хвилин.'),
    # the track count of the album page's header: the payload chooses the key by n == 1 and puts the number where %d is;
    # languages with more than two plural forms (pl, ru, uk) use a label that needs none ("Tracks: 12")
    _t('%d track', '%d 首歌曲', '%d 首歌曲', '%d 曲', '%d곡', '%d titre', '%d Titel',
       '%d canción', '%d brano', '%d เพลง', 'Utwory: %d', 'Песен: %d', 'Пісень: %d'),
    _t('%d tracks', '%d 首歌曲', '%d 首歌曲', '%d 曲', '%d곡', '%d titres', '%d Titel',
       '%d canciones', '%d brani', '%d เพลง', 'Utwory: %d', 'Песен: %d', 'Пісень: %d'),
    # The Playlists page (patch/playlists.c): the menu row that opens the stock Playlists page to delete (its multi-select button), and the
    # empty page's line. New / Import / Export playlist are the stock keys (STOCK).
    _t('Delete Playlists', '删除歌单', '刪除歌單', 'プレイリストを削除', '재생 목록 삭제', 'Supprimer des playlists', 'Playlists löschen',
       'Eliminar listas', 'Elimina playlist', 'ลบเพลย์ลิสต์', 'Usuń playlisty', 'Удалить плейлисты', 'Видалити плейлисти'),
    _t('No playlists', '没有歌单', '沒有歌單', 'プレイリストがありません', '재생 목록 없음', 'Aucune playlist', 'Keine Playlists',
       'No hay listas', 'Nessuna playlist', 'ไม่มีเพลย์ลิสต์', 'Brak playlist', 'Нет плейлистов', 'Немає плейлистів'),
    # The song count under the last row of the Songs page and its lists (patch/songs.c sg_foot_text; chosen by n == 1 as the track count above;
    # pl, ru, uk the label form that needs no plural)
    _t('%d song', '%d 首歌曲', '%d 首歌曲', '%d 曲', '%d곡', '%d titre', '%d Titel',
       '%d canción', '%d brano', '%d เพลง', 'Utwory: %d', 'Песен: %d', 'Пісень: %d'),
    _t('%d songs', '%d 首歌曲', '%d 首歌曲', '%d 曲', '%d곡', '%d titres', '%d Titel',
       '%d canciones', '%d brani', '%d เพลง', 'Utwory: %d', 'Песен: %d', 'Пісень: %d'),
    # the Songs page's line for an empty list (Favourites, a playlist ...; the library's empty line is "Update Local Music first")
    _t('No songs', '没有歌曲', '沒有歌曲', '曲がありません', '노래 없음', 'Aucun titre', 'Keine Titel',
       'Sin canciones', 'Nessun brano', 'ไม่มีเพลง', 'Brak utworów', 'Нет песен', 'Немає пісень'),
    # the iPod page's Now Playing screen (patch/ipod.c): the line for an empty player (the track's place in the queue is the neutral "3 / 12": the table format allows one %d a text)
    _t('Not Playing', '未在播放', '未在播放', '再生していません', '재생 중이 아님', 'Aucune lecture', 'Keine Wiedergabe',
       'Sin reproducción', 'Nessuna riproduzione', 'ไม่ได้เล่น', 'Nie odtwarza', 'Не воспроизводится', 'Не відтворюється'),
    # the iPod page's Settings list (patch/ipod.c): the labels and the values that cycle (Shuffle: Off / Songs; Repeat: Off / One / All; its last row is the shared Customize key)
    _t('Repeat', '重复', '重複', 'リピート', '반복', 'Répéter', 'Wiederholen',
       'Repetir', 'Ripeti', 'เล่นซ้ำ', 'Powtarzaj', 'Повтор', 'Повтор'),
    _t('Off', '关', '關', 'オフ', '끔', 'Désactivé', 'Aus',
       'Desactivado', 'Disattivato', 'ปิด', 'Wył.', 'Выкл.', 'Вимк.'),
    _t('One', '单曲', '單曲', '1曲', '한 곡', 'Un titre', 'Einzeln',
       'Una', 'Uno', 'เพลงเดียว', 'Jeden', 'Один', 'Один'),
    _t('All', '全部', '全部', 'すべて', '전체', 'Tous', 'Alle',
       'Todo', 'Tutti', 'ทั้งหมด', 'Wszystkie', 'Все', 'Усі'),
    # Podcasts (patch/podcasts.c, docs/modules/podcasts.md): the Extras item and the page's title, the two empty lines, the counts, the grey line of an episode
    _t('Podcasts', '播客', '播客', 'ポッドキャスト', '팟캐스트', 'Podcasts', 'Podcasts',
       'Pódcast', 'Podcast', 'พอดแคสต์', 'Podcasty', 'Подкасты', 'Подкасти'),
    _t('No podcasts. Copy a folder for each show into Podcasts on the card, or subscribe in Feeds, at the top right.',
       '没有播客。请在存储卡的 Podcasts 文件夹中为每个节目放一个文件夹，或在右上角的“订阅源”中订阅。', '沒有播客。請在記憶卡的 Podcasts 資料夾中為每個節目放一個資料夾，或在右上角的「訂閱源」中訂閱。',
       'ポッドキャストがありません。カードの Podcasts フォルダに番組ごとのフォルダをコピーするか、右上のフィードで登録してください。', '팟캐스트가 없습니다. 카드의 Podcasts 폴더에 프로그램마다 폴더를 복사하거나 오른쪽 위의 피드에서 구독하세요.',
       'Aucun podcast. Copiez un dossier par émission dans Podcasts sur la carte, ou abonnez-vous dans Flux, en haut à droite.', 'Keine Podcasts. Kopiere für jede Sendung einen Ordner in Podcasts auf der Karte oder abonniere oben rechts unter Feeds.',
       'Sin pódcast. Copia una carpeta por programa en Podcasts de la tarjeta, o suscríbete en Fuentes, arriba a la derecha.', 'Nessun podcast. Copia una cartella per ogni programma in Podcasts sulla scheda, oppure iscriviti in Feed, in alto a destra.',
       'ไม่มีพอดแคสต์ คัดลอกโฟลเดอร์ของแต่ละรายการไปที่ Podcasts บนการ์ด หรือติดตามในฟีดที่มุมขวาบน', 'Brak podcastów. Skopiuj folder dla każdego programu do Podcasts na karcie albo zasubskrybuj w Kanałach w prawym górnym rogu.',
       'Нет подкастов. Скопируйте по папке на каждое шоу в Podcasts на карте или подпишитесь в «Подписках» вверху справа.', 'Немає подкастів. Скопіюйте по теці для кожного шоу в Podcasts на картці або підпишіться в «Підписках» вгорі праворуч.'),
    _t('Nothing downloaded yet. Open Feeds, at the top right.', '还没有下载内容。请打开右上角的“订阅源”。', '尚未下載任何內容。請開啟右上角的「訂閱源」。',
       'まだダウンロードしたものはありません。右上のフィードを開いてください。', '아직 다운로드한 항목이 없습니다. 오른쪽 위의 피드를 여세요.',
       "Rien n'est encore téléchargé. Ouvrez Flux, en haut à droite.", 'Noch nichts geladen. Öffne oben rechts „Feeds“.',
       'Aún no hay descargas. Abre Fuentes, arriba a la derecha.', 'Ancora nulla di scaricato. Apri Feed, in alto a destra.',
       'ยังไม่มีรายการที่ดาวน์โหลด เปิดฟีดที่มุมขวาบน', 'Nic jeszcze nie pobrano. Otwórz Kanały w prawym górnym rogu.',
       'Пока ничего не загружено. Откройте «Подписки» вверху справа.', 'Ще нічого не завантажено. Відкрийте «Підписки» вгорі праворуч.'),
    # The refresh dialog of the Podcasts page (patch/podcasts.c pg_dlg_*; Cancel is the key above)
    _t('Refreshing Podcasts', '正在刷新播客', '正在更新 Podcast', 'ポッドキャストを更新中', '팟캐스트 새로고침 중', 'Actualisation des podcasts', 'Podcasts werden aktualisiert', 'Actualizando podcasts', 'Aggiornamento podcast',
       'กำลังรีเฟรชพอดแคสต์', 'Odświeżanie podcastów', 'Обновление подкастов', 'Оновлення подкастів'),
    _t('Cancelling…', '正在取消…', '正在取消…', 'キャンセル中…', '취소하는 중…', 'Annulation…', 'Wird abgebrochen …', 'Cancelando…', 'Annullamento…', 'กำลังยกเลิก…', 'Anulowanie…', 'Отмена…', 'Скасування…'),
    _t('%d of %d', '第 %d 个，共 %d 个', '第 %d 個，共 %d 個', '%d / %d', '%d / %d', '%d sur %d', '%d von %d', '%d de %d', '%d di %d', '%d จาก %d', '%d z %d', '%d из %d', '%d з %d'),
    _t('%d updated', '已更新 %d 个', '已更新 %d 個', '%d 件更新', '%d개 업데이트됨', '%d actualisés', '%d aktualisiert', '%d actualizados', '%d aggiornati', 'อัปเดต %d รายการ', 'Zaktualizowano: %d', 'Обновлено: %d', 'Оновлено: %d'),
    _t('%d updated, %d failed', '已更新 %d 个，%d 个失败', '已更新 %d 個，%d 個失敗', '%d 件更新、%d 件失敗', '%d개 업데이트됨, %d개 실패', '%d actualisés, %d échecs', '%d aktualisiert, %d fehlgeschlagen',
       '%d actualizados, %d con error', '%d aggiornati, %d non riusciti', 'อัปเดต %d รายการ ล้มเหลว %d', 'Zaktualizowano: %d, błędy: %d', 'Обновлено: %d, ошибок: %d', 'Оновлено: %d, помилок: %d'),
    _t('%d failed', '%d 个失败', '%d 個失敗', '%d 件失敗', '%d개 실패', '%d échecs', '%d fehlgeschlagen', '%d con error', '%d non riusciti', 'ล้มเหลว %d รายการ', 'Błędy: %d', 'Ошибок: %d', 'Помилок: %d'),
    _t('Cancelled', '已取消', '已取消', 'キャンセルしました', '취소됨', 'Annulé', 'Abgebrochen', 'Cancelado', 'Annullato', 'ยกเลิกแล้ว', 'Anulowano', 'Отменено', 'Скасовано'),
    _t('Cancelled, %d updated', '已取消，已更新 %d 个', '已取消，已更新 %d 個', 'キャンセル、%d 件更新', '취소됨, %d개 업데이트됨', 'Annulé, %d actualisés', 'Abgebrochen, %d aktualisiert', 'Cancelado, %d actualizados', 'Annullato, %d aggiornati',
       'ยกเลิกแล้ว อัปเดต %d รายการ', 'Anulowano, zaktualizowano: %d', 'Отменено, обновлено: %d', 'Скасовано, оновлено: %d'),
    # Podcasts, Feeds view and refresh (patch/podcasts.c, patch/pcnet.c; docs/modules/podcasts.md "Feeds")
    _t('Feeds', '订阅源', '訂閱源', 'フィード', '피드', 'Flux', 'Feeds', 'Fuentes', 'Feed', 'ฟีด', 'Kanały', 'Подписки', 'Підписки'),
    _t('Refresh All', '全部刷新', '全部更新', 'すべて更新', '모두 새로고침', 'Tout actualiser', 'Alle aktualisieren', 'Actualizar todo', 'Aggiorna tutto', 'รีเฟรชทั้งหมด', 'Odśwież wszystko', 'Обновить все', 'Оновити все'),
    _t('Refreshing', '正在刷新', '正在更新', '更新中', '새로고침 중', 'Actualisation', 'Aktualisiere', 'Actualizando', 'Aggiornamento', 'กำลังรีเฟรช', 'Odświeżanie', 'Обновление', 'Оновлення'),
    _t('Never refreshed', '从未刷新', '從未更新', '未更新', '새로고침 안 함', 'Jamais actualisé', 'Nie aktualisiert', 'Nunca actualizado', 'Mai aggiornato', 'ยังไม่เคยรีเฟรช', 'Nie odświeżano', 'Не обновлялось', 'Не оновлювалось'),
    _t('Up to date', '已是最新', '已是最新', '最新の状態', '최신 상태', 'À jour', 'Aktuell', 'Al día', 'Aggiornato', 'เป็นปัจจุบัน', 'Aktualne', 'Актуально', 'Актуально'),
    _t('%d new', '%d 个新节目', '%d 個新節目', '新着 %d 件', '새 에피소드 %d개', '%d nouveaux', '%d neue', '%d nuevos', '%d nuovi', 'ใหม่ %d', '%d nowe', 'Новых: %d', 'Нових: %d'),
    _t('Import shows', '导入节目', '匯入節目', '番組を読み込む', '프로그램 가져오기', 'Importer des podcasts', 'Podcasts importieren', 'Importar podcasts', 'Importa podcast', 'นำเข้าพอดแคสต์', 'Importuj podcasty', 'Импорт подкастов', 'Імпорт подкастів'),
    _t('Nothing new to import', '没有可导入的新内容', '沒有可匯入的新內容', '読み込む新しい項目はありません', '가져올 새 항목이 없습니다', 'Rien de nouveau à importer', 'Nichts Neues zu importieren',
       'Nada nuevo que importar', 'Niente di nuovo da importare', 'ไม่มีรายการใหม่ให้นำเข้า', 'Brak nowych pozycji do zaimportowania', 'Нечего импортировать', 'Немає що імпортувати'),
    _t('%d added', '已添加 %d 个', '已新增 %d 個', '%d 件追加', '%d개 추가됨', '%d ajoutés', '%d hinzugefügt', '%d añadidos', '%d aggiunti', 'เพิ่ม %d รายการ', 'Dodano: %d', 'Добавлено: %d', 'Додано: %d'),
    _t('No Wi-Fi', '无 Wi-Fi', '沒有 Wi-Fi', 'Wi-Fi 未接続', 'Wi-Fi 연결 없음', 'Pas de Wi-Fi', 'Kein WLAN', 'Sin Wi-Fi', 'Nessun Wi-Fi', 'ไม่มี Wi-Fi', 'Brak Wi-Fi', 'Нет Wi-Fi', 'Немає Wi-Fi'),
    _t('Set the date first', '请先设置日期', '請先設定日期', '先に日付を設定してください', '먼저 날짜를 설정하세요', "Réglez d'abord la date", 'Zuerst das Datum einstellen', 'Ajusta antes la fecha',
       'Imposta prima la data', 'ตั้งวันที่ก่อน', 'Najpierw ustaw datę', 'Сначала установите дату', 'Спочатку встановіть дату'),
    _t('Certificates missing', '缺少证书', '缺少憑證', '証明書がありません', '인증서 없음', 'Certificats manquants', 'Zertifikate fehlen', 'Faltan certificados', 'Certificati mancanti', 'ไม่พบใบรับรอง', 'Brak certyfikatów', 'Нет сертификатов', 'Немає сертифікатів'),
    _t('Certificate problem', '证书有问题', '憑證有問題', '証明書に問題があります', '인증서 문제', 'Problème de certificat', 'Zertifikatsproblem', 'Problema de certificado', 'Problema di certificato', 'ใบรับรองมีปัญหา', 'Problem z certyfikatem', 'Проблема с сертификатом', 'Проблема із сертифікатом'),
    _t("Can't connect", '无法连接', '無法連線', '接続できません', '연결할 수 없음', 'Connexion impossible', 'Keine Verbindung', 'No se puede conectar', 'Impossibile connettersi', 'เชื่อมต่อไม่ได้', 'Nie można połączyć', 'Не удаётся подключиться', 'Не вдається підключитися'),
    _t('Feed not found', '找不到订阅源', '找不到訂閱源', 'フィードが見つかりません', '피드를 찾을 수 없음', 'Flux introuvable', 'Feed nicht gefunden', 'Fuente no encontrada', 'Feed non trovato', 'ไม่พบฟีด', 'Nie znaleziono kanału', 'Подписка не найдена', 'Підписку не знайдено'),
    _t('Server error', '服务器错误', '伺服器錯誤', 'サーバーエラー', '서버 오류', 'Erreur du serveur', 'Serverfehler', 'Error del servidor', 'Errore del server', 'เซิร์ฟเวอร์ผิดพลาด', 'Błąd serwera', 'Ошибка сервера', 'Помилка сервера'),
    _t('Not a podcast feed', '不是播客订阅源', '不是 Podcast 訂閱源', 'ポッドキャストのフィードではありません', '팟캐스트 피드가 아닙니다', "Ce n'est pas un flux de podcast", 'Kein Podcast-Feed', 'No es una fuente de podcast',
       'Non è un feed podcast', 'ไม่ใช่ฟีดพอดแคสต์', 'To nie jest kanał podcastu', 'Это не подписка на подкаст', 'Це не стрічка подкасту'),
    _t('%d MB', '%dMB', '%dMB', '%dMB', '%dMB', *(['%d MB'] * 8)),   # the size ending a remote episode's grey line (no space in the CJK languages)
    # Episode downloads (patch/podcasts.c, patch/pcnet.c; docs/modules/podcasts.md "Downloads"): the grey line of an episode that is not on the card, "Failed: <reason>" (the reasons above and these), and the Feeds row
    _t('Downloading', '正在下载', '正在下載', 'ダウンロード中', '다운로드 중', 'Téléchargement', 'Wird geladen', 'Descargando', 'Download in corso', 'กำลังดาวน์โหลด', 'Pobieranie', 'Загрузка', 'Завантаження'),
    _t('Waiting', '等待中', '等待中', '待機中', '대기 중', 'En attente', 'Wartet', 'En espera', 'In attesa', 'รอคิว', 'Oczekuje', 'Ожидание', 'Очікування'),
    _t('Paused', '已暂停', '已暫停', '一時停止中', '일시 중지됨', 'En pause', 'Pausiert', 'En pausa', 'In pausa', 'หยุดชั่วคราว', 'Wstrzymano', 'Приостановлено', 'Призупинено'),
    _t('Failed', '失败', '失敗', '失敗', '실패', 'Échec', 'Fehler', 'Error', 'Errore', 'ล้มเหลว', 'Błąd', 'Сбой', 'Збій'),
    _t('Not found', '未找到', '找不到', '見つかりません', '찾을 수 없음', 'Introuvable', 'Nicht gefunden', 'No encontrado', 'Non trovato', 'ไม่พบ', 'Nie znaleziono', 'Не найдено', 'Не знайдено'),
    _t('Not audio', '不是音频', '不是音訊', '音声ではありません', '오디오가 아님', "Pas de l'audio", 'Kein Audio', 'No es audio', 'Non è audio', 'ไม่ใช่เสียง', 'To nie audio', 'Не аудио', 'Не аудіо'),
    _t('Card is full', '存储卡已满', '記憶卡已滿', 'カードがいっぱいです', '카드가 가득 참', 'Carte pleine', 'Karte voll', 'Tarjeta llena', 'Scheda piena', 'การ์ดเต็ม', 'Karta pełna', 'Карта заполнена', 'Картка заповнена'),
    _t('Queue is full', '队列已满', '佇列已滿', 'キューがいっぱいです', '대기열이 가득 참', "File d'attente pleine", 'Warteschlange voll', 'Cola llena', 'Coda piena', 'คิวเต็ม', 'Kolejka pełna', 'Очередь заполнена', 'Черга заповнена'),
    # The Downloads level and the select mode of the Show level (patch/podcasts.c; "N Selected", "Select All" and "Delete" are the Songs page's keys)
    _t('No downloads', '没有下载', '沒有下載', 'ダウンロードはありません', '다운로드 없음', 'Aucun téléchargement', 'Keine Downloads', 'Sin descargas', 'Nessun download', 'ไม่มีการดาวน์โหลด', 'Brak pobrań', 'Нет загрузок', 'Немає завантажень'),
    _t('Delete the selected episodes?', '删除所选节目？', '刪除所選節目？', '選択したエピソードを削除しますか？', '선택한 에피소드를 삭제할까요?', 'Supprimer les épisodes sélectionnés ?', 'Ausgewählte Folgen löschen?',
       '¿Eliminar los episodios seleccionados?', 'Eliminare gli episodi selezionati?', 'ลบตอนที่เลือกหรือไม่?', 'Usunąć wybrane odcinki?', 'Удалить выбранные выпуски?', 'Видалити вибрані випуски?'),
    _t('Remove the selected downloads?', '移除所选下载？', '移除所選下載？', '選択したダウンロードを削除しますか？', '선택한 다운로드를 제거할까요?', 'Retirer les téléchargements sélectionnés ?', 'Ausgewählte Downloads entfernen?',
       '¿Quitar las descargas seleccionadas?', 'Rimuovere i download selezionati?', 'ลบการดาวน์โหลดที่เลือกหรือไม่?', 'Usunąć wybrane pobrania?', 'Удалить выбранные загрузки?', 'Видалити вибрані завантаження?'),
    _t('The playing episode was kept', '正在播放的节目已保留', '正在播放的節目已保留', '再生中の項目は残しました', '재생 중인 에피소드는 유지되었습니다', 'L’épisode en lecture a été conservé', 'Die laufende Folge wurde behalten',
       'Se conservó el episodio en reproducción', 'Episodio in corso mantenuto', 'เก็บตอนที่กำลังเล่นไว้', 'Odtwarzany odcinek został zachowany', 'Воспроизводимый выпуск сохранён', 'Епізод, що відтворюється, збережено'),
    _t('Downloads', '下载', '下載', 'ダウンロード', '다운로드', 'Téléchargements', 'Downloads', 'Descargas', 'Download', 'ดาวน์โหลด', 'Pobrane', 'Загрузки', 'Завантаження'),
    _t('No subscriptions. List one feed address per line in subscriptions.txt in Podcasts on the card, then open Feeds again.',
       '没有订阅。在存储卡 Podcasts 文件夹的 subscriptions.txt 中每行写一个订阅源地址，然后重新打开“订阅源”。', '沒有訂閱。在記憶卡 Podcasts 資料夾的 subscriptions.txt 中每行寫一個訂閱源網址，然後重新開啟「訂閱源」。',
       'フィードがありません。カードの Podcasts フォルダの subscriptions.txt に、1行に1つずつフィードのアドレスを書き、もう一度フィードを開いてください。',
       '구독이 없습니다. 카드의 Podcasts 폴더에 있는 subscriptions.txt에 한 줄에 피드 주소를 하나씩 적고 피드를 다시 여세요.',
       'Aucun abonnement. Écrivez une adresse de flux par ligne dans subscriptions.txt, dans Podcasts sur la carte, puis rouvrez Flux.',
       'Keine Abos. Schreibe pro Zeile eine Feed-Adresse in subscriptions.txt im Ordner Podcasts auf der Karte und öffne dann Feeds erneut.',
       'No hay suscripciones. Escribe una dirección de fuente por línea en subscriptions.txt, en Podcasts de la tarjeta, y vuelve a abrir Fuentes.',
       'Nessun abbonamento. Scrivi un indirizzo di feed per riga in subscriptions.txt, in Podcast sulla scheda, poi riapri Feed.',
       'ยังไม่มีการติดตาม เขียนที่อยู่ฟีดบรรทัดละหนึ่งรายการในไฟล์ subscriptions.txt ในโฟลเดอร์ Podcasts บนการ์ด แล้วเปิดฟีดอีกครั้ง',
       'Brak subskrypcji. Wpisz po jednym adresie kanału w wierszu w pliku subscriptions.txt w folderze Podcasts na karcie, a potem otwórz Kanały ponownie.',
       'Нет подписок. Впишите по одному адресу ленты в строке в файл subscriptions.txt в папке Podcasts на карте и снова откройте «Подписки».',
       'Немає підписок. Запишіть по одній адресі стрічки в рядку у файлі subscriptions.txt у папці Podcasts на картці й знову відкрийте «Підписки».'),
    _t('No episodes yet. Refresh the feed in Feeds.', '暂无节目。请在“订阅源”中刷新。', '暫無節目。請在「訂閱源」中更新。', 'エピソードはまだありません。フィードで更新してください。', '아직 에피소드가 없습니다. 피드에서 새로고침하세요.',
       "Aucun épisode pour l'instant. Actualisez le flux dans Flux.", 'Noch keine Folgen. Aktualisiere den Feed unter Feeds.', 'Aún no hay episodios. Actualiza la fuente en Fuentes.',
       'Ancora nessun episodio. Aggiorna il feed in Feed.', 'ยังไม่มีตอน รีเฟรชฟีดในหน้าฟีด', 'Brak odcinków. Odśwież kanał w Kanałach.', 'Эпизодов пока нет. Обновите подписку в «Подписках».', 'Епізодів поки немає. Оновіть підписку в «Підписках».'),
    _t('No downloaded episodes', '没有已下载的节目', '沒有已下載的節目', 'ダウンロード済みのエピソードがありません', '다운로드한 에피소드가 없습니다', 'Aucun épisode téléchargé', 'Keine geladenen Folgen',
       'Sin episodios descargados', 'Nessun episodio scaricato', 'ไม่มีตอนที่ดาวน์โหลด', 'Brak pobranych odcinków', 'Нет загруженных выпусков', 'Немає завантажених випусків'),
    _t('%d episode', '%d 个节目', '%d 個節目', '%d エピソード', '에피소드 %d개', '%d épisode', '%d Folge',
       '%d episodio', '%d episodio', '%d ตอน', 'Odcinki: %d', 'Выпусков: %d', 'Випусків: %d'),
    _t('%d episodes', '%d 个节目', '%d 個節目', '%d エピソード', '에피소드 %d개', '%d épisodes', '%d Folgen',
       '%d episodios', '%d episodi', '%d ตอน', 'Odcinki: %d', 'Выпусков: %d', 'Випусків: %d'),
    _t('%d min left', '剩余 %d 分钟', '剩餘 %d 分鐘', '残り %d 分', '%d분 남음', '%d min restantes', 'Noch %d Min.',
       'Quedan %d min', '%d min rimasti', 'เหลือ %d นาที', 'Zostało %d min', 'Осталось %d мин', 'Ще %d хв'),
    _t('%d min', '%d 分钟', '%d 分鐘', '%d 分', '%d분', '%d min', '%d Min.',
       '%d min', '%d min', '%d นาที', '%d min', '%d мин', '%d хв'),
    _t('Played', '已播放', '已播放', '再生済み', '재생함', 'Lu', 'Gehört',
       'Reproducido', 'Riprodotto', 'เล่นแล้ว', 'Odtworzono', 'Прослушано', 'Прослухано'),
    # Now Playing's info page labels (patch/nowplaying.c np_info): stock's "Genres" (the plural tab name) and "Era"
    # (a decade in several tables, "age" in Korean) become "Genre: ..." and "Year: ..."
    _t('Genre', '风格', '風格', 'ジャンル', '장르', 'Genre', 'Genre',
       'Género', 'Genere', 'ประเภท', 'Gatunek', 'Жанр', 'Жанр'),
    _t('Year', '年份', '年份', '年', '연도', 'Année', 'Jahr',
       'Año', 'Anno', 'ปี', 'Rok', 'Год', 'Рік'),
    # Screenshot (the Extras row; the toasts of patch/shot.c: the countdown is the fixed 5 s of SHOT_SECONDS)
    _t('Screenshot', '截图', '截圖', 'スクリーンショット', '스크린샷', "Capture d'écran", 'Screenshot',
       'Captura de pantalla', 'Screenshot', 'ภาพหน้าจอ', 'Zrzut ekranu', 'Скриншот', 'Знімок екрана'),
    _t('Take a screenshot in 5 s?', '5 秒后截图？', '5 秒後截圖？', '5秒後にスクリーンショットを撮りますか？', '5초 후 스크린샷을 찍을까요?',
       'Prendre une capture dans 5 s ?', 'Screenshot in 5 s aufnehmen?', '¿Hacer una captura en 5 s?', 'Fare uno screenshot tra 5 s?',
       'ถ่ายภาพหน้าจอใน 5 วินาทีไหม', 'Zrobić zrzut ekranu za 5 s?', 'Сделать скриншот через 5 с?', 'Зробити знімок через 5 с?'),
    _t('Cancel the screenshot?', '取消截图？', '取消截圖？', 'スクリーンショットを取り消しますか？', '스크린샷을 취소할까요?',
       'Annuler la capture ?', 'Screenshot abbrechen?', '¿Cancelar la captura?', 'Annullare lo screenshot?',
       'ยกเลิกการถ่ายภาพหน้าจอไหม', 'Anulować zrzut ekranu?', 'Отменить скриншот?', 'Скасувати знімок?'),
    _t('Screenshot saved', '截图已保存', '截圖已儲存', 'スクリーンショットを保存', '스크린샷 저장됨', 'Capture enregistrée', 'Screenshot gespeichert',
       'Captura guardada', 'Screenshot salvato', 'บันทึกภาพหน้าจอแล้ว', 'Zrzut zapisany', 'Скриншот сохранён', 'Знімок збережено'),
    _t('Screenshot failed', '截图失败', '截圖失敗', 'スクリーンショット失敗', '스크린샷 실패', 'Échec de la capture', 'Screenshot fehlgeschlagen',
       'Error en la captura', 'Screenshot non riuscito', 'ถ่ายภาพหน้าจอไม่สำเร็จ', 'Zrzut nieudany', 'Не удалось снять экран', 'Не вдалося зробити знімок'),
    # Network Probe (Customize > Developer; patch/probe.c)
    _t('Network Probe', '网络探测', '網絡探測', 'ネットワーク診断', '네트워크 점검', 'Test réseau', 'Netzwerktest',
       'Prueba de red', 'Test di rete', 'ทดสอบเครือข่าย', 'Test sieci', 'Проверка сети', 'Перевірка мережі'),
    _t('Run the network probe? It takes about 7 minutes and writes m1plus-probe.log to the card. Turn the screen off after it starts.',
       '运行网络探测？约需 7 分钟，并在存储卡写入 m1plus-probe.log。启动后请关闭屏幕。',
       '執行網絡探測？約需 7 分鐘，並在記憶卡寫入 m1plus-probe.log。啟動後請關閉螢幕。',
       'ネットワーク診断を実行しますか？約7分かかり、カードに m1plus-probe.log を書き込みます。開始後は画面を消してください。',
       '네트워크 점검을 실행할까요? 약 7분 걸리며 카드에 m1plus-probe.log를 기록합니다. 시작 후 화면을 끄세요.',
       "Lancer le test réseau ? Il dure environ 7 minutes et écrit m1plus-probe.log sur la carte. Éteignez l'écran après le démarrage.",
       'Netzwerktest starten? Er dauert etwa 7 Minuten und schreibt m1plus-probe.log auf die Karte. Danach den Bildschirm ausschalten.',
       '¿Iniciar la prueba de red? Tarda unos 7 minutos y escribe m1plus-probe.log en la tarjeta. Apaga la pantalla al empezar.',
       "Avviare il test di rete? Dura circa 7 minuti e scrive m1plus-probe.log sulla scheda. Spegni lo schermo dopo l'avvio.",
       'เริ่มทดสอบเครือข่ายไหม ใช้เวลาประมาณ 7 นาที และเขียน m1plus-probe.log ลงการ์ด เมื่อเริ่มแล้วให้ปิดหน้าจอ',
       'Uruchomić test sieci? Trwa ok. 7 minut i zapisuje m1plus-probe.log na karcie. Po starcie wyłącz ekran.',
       'Запустить проверку сети? Она займёт около 7 минут и запишет m1plus-probe.log на карту. После запуска выключите экран.',
       'Запустити перевірку мережі? Вона триватиме близько 7 хвилин і запише m1plus-probe.log на картку. Після запуску вимкніть екран.'),
    _t('Network probe is running', '网络探测运行中', '網絡探測執行中', 'ネットワーク診断を実行中', '네트워크 점검 중', 'Test réseau en cours', 'Netzwerktest läuft',
       'Prueba de red en curso', 'Test di rete in corso', 'กำลังทดสอบเครือข่าย', 'Test sieci trwa', 'Проверка сети идёт', 'Перевірка мережі триває'),
    _t('Network probe failed', '网络探测失败', '網絡探測失敗', 'ネットワーク診断に失敗', '네트워크 점검 실패', 'Échec du test réseau', 'Netzwerktest fehlgeschlagen',
       'Error en la prueba de red', 'Test di rete non riuscito', 'ทดสอบเครือข่ายไม่สำเร็จ', 'Test sieci nieudany', 'Проверка сети не удалась', 'Перевірка мережі не вдалася'),
    # Now Playing's More menu (patch/playmore.c): the row that opens the second page (and that page's back header), the short
    # Playback speed label (stock: "Multiple Speed", wider than the room before the four speed badges) and the 14 px note under it
    _t('More', '更多', '更多', 'その他', '더 보기', 'Plus', 'Mehr',
       'Más', 'Altro', 'เพิ่มเติม', 'Więcej', 'Ещё', 'Ще'),
    _t('Speed', '倍速', '倍速', '再生速度', '재생 속도', 'Vitesse', 'Tempo',
       'Velocidad', 'Velocità', 'ความเร็ว', 'Prędkość', 'Скорость', 'Швидкість'),
    # Now Playing's More sheet: the row that opens the landscape cassette page (patch/tape.c, docs/modules/tape.md); the page's own name is the same text
    _t('Cassette Mode', '磁带模式', '錄音帶模式', 'カセットモード', '카세트 모드', 'Mode cassette', 'Kassettenmodus',
       'Modo casete', 'Modalità cassetta', 'โหมดเทป', 'Tryb kasety', 'Режим кассеты', 'Режим касети'),
    # Customize > Cassette Mode: the theme row and its three values
    _t('Cassette Theme', '磁带主题', '錄音帶主題', 'カセットテーマ', '카세트 테마', 'Thème cassette', 'Kassettendesign',
       'Tema del casete', 'Tema cassetta', 'ธีมเทป', 'Motyw kasety', 'Тема кассеты', 'Тема касети'),
    _t('Normal', '标准', '標準', '標準', '기본', 'Normal', 'Normal',
       'Normal', 'Normale', 'ปกติ', 'Normalny', 'Обычная', 'Звичайна'),
    _t('Chrome', '铬色', '鉻色', 'クローム', '크롬', 'Chrome', 'Chrom',
       'Cromo', 'Cromo', 'โครเมียม', 'Chrom', 'Хром', 'Хром'),
    _t('Metal', '金属', '金屬', 'メタル', '메탈', 'Métal', 'Metall',
       'Metal', 'Metallo', 'โลหะ', 'Metal', 'Металл', 'Метал'),
    # The Songs page (patch/songs.c): the Play pill (Shuffle is above), the select mode's navbar ("N Selected", the Select All text button) and its
    # Delete pill. The count goes where %d is (the payload puts the number there). Add to playlist is the stock key (STOCK).
    _t('Play', '播放', '播放', '再生', '재생', 'Lire', 'Abspielen',
       'Reproducir', 'Riproduci', 'เล่น', 'Odtwórz', 'Играть', 'Грати'),
    _t('Select All', '全选', '全選', 'すべて選択', '모두 선택', 'Tout choisir', 'Alle wählen',
       'Todo', 'Tutti', 'เลือกทั้งหมด', 'Wszystko', 'Выбрать все', 'Вибрати все'),
    _t('Add to Playlist', '加入歌单', '加入歌單', 'リストに追加', '목록에 추가', 'Ajouter', 'Hinzufügen',
       'Añadir', 'Aggiungi', 'เพิ่ม', 'Dodaj', 'Добавить', 'Додати'),   # (the stock key's texts are longer than the select bar's 145 px pill holds beside its glyph: German 30 characters, Japanese 144 px)
    _t('Delete', '删除', '刪除', '削除', '삭제', 'Supprimer', 'Löschen',
       'Eliminar', 'Elimina', 'ลบ', 'Usuń', 'Удалить', 'Видалити'),
    _t('%d Selected', '已选 %d 项', '已選 %d 項', '%d 件選択', '%d개 선택', '%d choisis', '%d gewählt',
       '%d elegidas', '%d scelti', 'เลือก %d', 'Wybrano: %d', 'Выбрано: %d', 'Вибрано: %d'),
    _t('Files below 48 kHz only', '仅对 48kHz 以下有效', '僅對 48kHz 以下有效', '48kHz未満のみ', '48kHz 미만 파일만', 'Fichiers < 48 kHz seulement', 'Nur Dateien unter 48 kHz',
       'Solo archivos bajo 48 kHz', 'Solo file sotto 48 kHz', 'เฉพาะไฟล์ต่ำกว่า 48 kHz', 'Tylko pliki poniżej 48 kHz', 'Только файлы ниже 48 кГц', 'Лише файли нижче 48 кГц'),
    # The Daily Mix card of the Home menu (patch/dailymix.c, docs/modules/dailymix.md): the section header (the Recently Played shelf's style), the card title AND the
    # Customize > Home Screen switch row ("Daily Mix": the card breaks it at its first space into two lines, a word with no space is one line on the bottom one),
    # the action row, the card's artists line ("%s and more": a printf template of one %s) and the join of two names ("%s, %s": applied name by name). Not literal in every language
    # (fr "Mix du jour", de "Tagesmix", it "Mix del giorno", ru "Микс дня"); they want a native-speaker pass.
    _t('Made for You', '为你推荐', '為你推薦', 'あなたへのおすすめ', '맞춤 추천', 'Pour vous', 'Für dich',
       'Para ti', 'Per te', 'สำหรับคุณ', 'Dla Ciebie', 'Для вас', 'Для вас'),
    _t('Daily Mix', '每日精选', '每日精選', 'デイリー ミックス', '데일리 믹스', 'Mix du jour', 'Tagesmix',
       'Mix diario', 'Mix del giorno', 'มิกซ์ประจำวัน', 'Miks dnia', 'Микс дня', 'Мікс дня'),
    _t('Regenerate Daily Mix', '重新生成每日精选', '重新產生每日精選', 'デイリー ミックス再生成', '데일리 믹스 다시 만들기', 'Régénérer le Mix du jour', 'Tagesmix neu erstellen',
       'Regenerar Mix diario', 'Rigenera Mix del giorno', 'สร้างมิกซ์ประจำวันใหม่', 'Odśwież Miks dnia', 'Обновить Микс дня', 'Оновити Мікс дня'),
    _t('%s and more', '%s等', '%s等', '%s など', '%s 등', '%s et plus', '%s und mehr',
       '%s y más', '%s e altri', '%s และอื่นๆ', '%s i inni', '%s и другие', '%s та інші'),
    _t('%s, %s', *('%s、%s', '%s、%s', '%s、%s') + ('%s, %s',) * 9),
    # The Daily Mix page (patch/dailymix.c dp_*, docs/modules/dailymix.md "The page"): the Updated line under the subtitle (today, yesterday, else "Updated <ISO date>": the date is
    # YYYY-MM-DD in every language, so no month names), the white pill's text, and the description under the buttons (two lines of 288 px at 15 px in every language).
    # A native-speaker pass is wanted.
    _t('Updated today', '今天更新', '今天更新', '今日更新', '오늘 업데이트됨', 'Mis à jour aujourd\'hui', 'Heute aktualisiert',
       'Actualizado hoy', 'Aggiornato oggi', 'อัปเดตวันนี้', 'Zaktualizowano dzisiaj', 'Обновлено сегодня', 'Оновлено сьогодні'),
    _t('Updated yesterday', '昨天更新', '昨天更新', '昨日更新', '어제 업데이트됨', 'Mis à jour hier', 'Gestern aktualisiert',
       'Actualizado ayer', 'Aggiornato ieri', 'อัปเดตเมื่อวาน', 'Zaktualizowano wczoraj', 'Обновлено вчера', 'Оновлено вчора'),
    _t('Updated %s', '%s 更新', '%s 更新', '%s に更新', '%s 업데이트됨', 'Mis à jour le %s', 'Aktualisiert am %s',
       'Actualizado el %s', 'Aggiornato il %s', 'อัปเดต %s', 'Zaktualizowano %s', 'Обновлено %s', 'Оновлено %s'),
    _t('Play', '播放', '播放', '再生', '재생', 'Lecture', 'Wiedergabe',
       'Reproducir', 'Riproduci', 'เล่น', 'Odtwórz', 'Играть', 'Грати'),
    _t('Songs you love and some to rediscover, made fresh every day.', '你喜爱的歌曲，加上一些值得重新发现的好歌，每天为你更新。',
       '你喜愛的歌曲，加上一些值得重新發現的好歌，每天為你更新。', 'お気に入りの曲と、もう一度聴きたい曲を、毎日お届けします。',
       '좋아하는 노래와 다시 들어볼 노래를 매일 새롭게 만들어 드려요.', 'Les titres que vous aimez et des pépites à redécouvrir, renouvelés chaque jour.',
       'Songs, die du liebst, und einige zum Wiederentdecken – jeden Tag neu.', 'Canciones que te encantan y otras para redescubrir, renovadas cada día.',
       'Brani che ami e altri da riscoprire, rinnovati ogni giorno.', 'เพลงที่คุณรักและเพลงให้ค้นพบใหม่ สร้างสรรค์ใหม่ทุกวัน',
       'Utwory, które kochasz, i kilka do odkrycia na nowo, odświeżane codziennie.', 'Песни, которые вы любите, и несколько для нового открытия: каждый день заново.',
       'Пісні, які ви любите, і кілька для нового відкриття: щодня наново.'),
    # The section headers of the Extras page and Customize > Extras (pod_pages.EXTRAS_GROUPS): Play is the key above. The stock tables have no key for these
    # (their "Library" is part of longer texts). Library follows the terms of the stock tables (曲库, Datenbank, librería ...). A native-speaker pass is wanted.
    _t('Library', '曲库', '曲庫', 'ライブラリ', '라이브러리', 'Bibliothèque', 'Datenbank',
       'Librería', 'Libreria', 'คลังเพลง', 'Biblioteka', 'Библиотека', 'Медіатека'),
    _t('Collections', '合集', '合集', 'コレクション', '컬렉션', 'Collections', 'Sammlungen',
       'Colecciones', 'Raccolte', 'คอลเลกชัน', 'Kolekcje', 'Коллекции', 'Колекції'),
    _t('Tools', '工具', '工具', 'ツール', '도구', 'Outils', 'Werkzeuge',
       'Herramientas', 'Strumenti', 'เครื่องมือ', 'Narzędzia', 'Инструменты', 'Інструменти'),
])
# The Podcasts page's dates (patch/pcmodel.c pc_when, docs/modules/podcasts.md "The date"): Apple Podcasts' "Just now", "4m ago", "4h ago", "4d ago", "Oct 23", "Oct 23, 2025". A month
# text has its one %d (the day) where the language puts it; the year follows as ", %d". These keys do not start with %d, so DATE_KEYS lets the %d test of the tables know them.
_MONTH_KEYS = ('Jan %d', 'Feb %d', 'Mar %d', 'Apr %d', 'May %d', 'Jun %d', 'Jul %d', 'Aug %d', 'Sep %d', 'Oct %d', 'Nov %d', 'Dec %d')
_MONTHS = {   # locale -> the twelve month texts
    'zh_CN': [f'{m}月%d日' for m in range(1, 13)], 'zh_HK': [f'{m}月%d日' for m in range(1, 13)], 'ja_JP': [f'{m}月%d日' for m in range(1, 13)],
    'ko_KR': [f'{m}월 %d일' for m in range(1, 13)],
    'fr_FR': [f'{x} %d' for x in ('janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.')],
    'ge_DE': [f'%d. {x}' for x in ('Jan.', 'Feb.', 'März', 'Apr.', 'Mai', 'Juni', 'Juli', 'Aug.', 'Sept.', 'Okt.', 'Nov.', 'Dez.')],
    'sp_ES': [f'%d {x}' for x in ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic')],
    'it_IT': [f'%d {x}' for x in ('gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic')],
    'th_TH': [f'%d {x}' for x in ('ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.')],
    'po_PL': [f'%d {x}' for x in ('sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru')],
    'ru_RU': [f'%d {x}' for x in ('янв.', 'февр.', 'мар.', 'апр.', 'мая', 'июн.', 'июл.', 'авг.', 'сент.', 'окт.', 'нояб.', 'дек.')],
    'uk_UK': [f'%d {x}' for x in ('січ.', 'лют.', 'бер.', 'квіт.', 'трав.', 'черв.', 'лип.', 'серп.', 'вер.', 'жовт.', 'лист.', 'груд.')],
}
TEXT.update(_t(k, *[_MONTHS[loc][i] for loc in _L]) for i, k in enumerate(_MONTH_KEYS))
TEXT.update([
    _t(', %d', '，%d年', '，%d年', ', %d年', ', %d년', ', %d', ', %d', ', %d', ', %d', ', %d', ', %d', ', %d', ', %d'),
    _t('Just now', '刚刚', '剛剛', 'たった今', '방금', 'À l’instant', 'Gerade eben', 'Ahora mismo', 'Adesso', 'เมื่อสักครู่', 'Przed chwilą', 'Только что', 'Щойно'),
    _t('%dm ago', '%d分钟前', '%d分鐘前', '%d分前', '%d분 전', 'il y a %d min', 'vor %d Min.', 'hace %d min', '%d min fa', '%d นาทีที่แล้ว', '%d min temu', '%d мин назад', '%d хв тому'),
    _t('%dh ago', '%d小时前', '%d小時前', '%d時間前', '%d시간 전', 'il y a %d h', 'vor %d Std.', 'hace %d h', '%d h fa', '%d ชั่วโมงที่แล้ว', '%d godz. temu', '%d ч назад', '%d год тому'),
    _t('%dd ago', '%d天前', '%d天前', '%d日前', '%d일 전', 'il y a %d j', 'vor %d T.', 'hace %d d', '%d g fa', '%d วันที่แล้ว', '%d dn. temu', '%d дн. назад', '%d дн. тому'),
])
DATE_KEYS = _MONTH_KEYS + (', %d', '%dm ago', '%dh ago', '%dd ago')   # keys with a %d that do not start with it (the tables test, test/pod/i18n.py)
DPAGE_KEYS = ('Updated today', 'Updated yesterday', 'Updated %s', 'Play', 'Songs you love and some to rediscover, made fresh every day.')   # the Daily Mix page's keys
DAILY_KEYS =('Made for You', 'Daily Mix', 'Regenerate Daily Mix', '%s and more', '%s, %s')     # the card's keys (tools/pod_dailymix.py TEXT)

KEYS = sorted(TEXT)


def english(key):
    """The English text a key stands for (our keys are their own English; stock keys come from STOCK)."""
    return TEXT[key]['en_US'] if key in TEXT else STOCK[key]


BRANDS = ('M1+ Music', 'Tidal', 'Pod')     # shown as they are, no key


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
