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
    'msg_newplaylists': 'Enter a playlist name',   # the New playlist keyboard's placeholder (the stock keyboard dialog's own hint, patch/playlists.c)
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
    _t('Boot to M1+ Music', '开机进入 M1+ Music', '開機進入 M1+ Music', '起動時に M1+ Music', '부팅 시 M1+ Music', 'Lancer M1+ Music', 'Start mit M1+ Music',
       'Iniciar M1+ Music', 'Avvio in M1+ Music', 'บูตเข้า M1+ Music', 'Start w M1+ Music', 'Запуск M1+ Music', 'Запуск M1+ Music'),
    _t('Settings', '设置', '設定', '設定', '설정', 'Réglages', 'Einstellungen',
       'Ajustes', 'Impostazioni', 'การตั้งค่า', 'Ustawienia', 'Настройки', 'Налаштування'),
    _t('Developer', '开发者', '開發者', '開発者向け', '개발자', 'Développeur', 'Entwickler',
       'Desarrollador', 'Sviluppatore', 'นักพัฒนา', 'Programista', 'Разработчик', 'Розробник'),
    _t('Playback', '播放', '播放', '再生', '재생', 'Lecture', 'Wiedergabe',
       'Reproducción', 'Riproduzione', 'การเล่น', 'Odtwarzanie', 'Воспроизведение', 'Відтворення'),
    # Settings (docs/modules/settings.md): the top page's rows, headers and notes. Rows with a value at the right (Play Mode, Language, Album Order, Theme) have short labels: the value takes the room.
    _t('Wi-Fi', 'Wi-Fi', 'Wi-Fi', 'Wi-Fi', 'Wi-Fi', 'Wi-Fi', 'Wi-Fi',
       'Wi-Fi', 'Wi-Fi', 'Wi-Fi', 'Wi-Fi', 'Wi-Fi', 'Wi-Fi'),
    _t('Bluetooth', '蓝牙', '藍牙', 'Bluetooth', '블루투스', 'Bluetooth', 'Bluetooth',
       'Bluetooth', 'Bluetooth', 'บลูทูธ', 'Bluetooth', 'Bluetooth', 'Bluetooth'),
    _t('On', '开', '開', 'オン', '켜짐', 'Activé', 'An',
       'Activado', 'Attivo', 'เปิด', 'Wł.', 'Вкл.', 'Увімк.'),
    _t('Off', '关', '關', 'オフ', '꺼짐', 'Désactivé', 'Aus',
       'Desactivado', 'Disattivo', 'ปิด', 'Wył.', 'Выкл.', 'Вимк.'),
    _t('Menu & Extras', '菜单与附加功能', '選單與附加功能', 'メニューとエクストラ', '메뉴 및 부가 기능', 'Menu et extras', 'Menü & Extras',
       'Menú y extras', 'Menu ed extra', 'เมนูและเพิ่มเติม', 'Menu i dodatki', 'Меню и дополнения', 'Меню й додатки'),
    _t('Play Mode', '播放模式', '播放模式', '再生モード', '재생 모드', 'Lecture', 'Modus',
       'Modo', 'Modalità', 'โหมดเล่น', 'Tryb', 'Режим', 'Режим'),
    _t('EQ', 'EQ', 'EQ', 'EQ', 'EQ', 'EQ', 'EQ',
       'EQ', 'EQ', 'EQ', 'EQ', 'EQ', 'EQ'),
    _t('All Playback Settings', '全部播放设置', '全部播放設定', 'すべての再生設定', '모든 재생 설정', 'Réglages de lecture', 'Wiedergabe-Optionen',
       'Ajustes de reproducción', 'Impostazioni riproduzione', 'การตั้งค่าการเล่นทั้งหมด', 'Ustawienia odtwarzania', 'Параметры плеера', 'Параметри плеєра'),
    _t('System', '系统', '系統', 'システム', '시스템', 'Système', 'System',
       'Sistema', 'Sistema', 'ระบบ', 'System', 'Система', 'Система'),
    _t('Display', '显示', '顯示', 'ディスプレイ', '디스플레이', 'Affichage', 'Anzeige',
       'Pantalla', 'Display', 'การแสดงผล', 'Wyświetlacz', 'Дисплей', 'Дисплей'),
    _t('Language', '语言', '語言', '言語', '언어', 'Langue', 'Sprache',
       'Idioma', 'Lingua', 'ภาษา', 'Język', 'Язык', 'Мова'),
    _t('About', '关于', '關於', '概要', '정보', 'À propos', 'Info',
       'Acerca de', 'Info', 'เกี่ยวกับ', 'Informacje', 'О плеере', 'Про пристрій'),
    _t('All System Settings', '全部系统设置', '全部系統設定', 'すべてのシステム設定', '모든 시스템 설정', 'Réglages système', 'Systemeinstellungen',
       'Ajustes del sistema', 'Impostazioni di sistema', 'การตั้งค่าระบบทั้งหมด', 'Ustawienia systemowe', 'Системные настройки', 'Налаштування системи'),
    # Settings > System > About (our own page, docs/modules/settings.md "About"): the section headers and the row labels (values are data; the credits' names and licences are brands)
    _t('Firmware', '固件版本', '韌體版本', 'ファームウェア', '펌웨어', 'Firmware', 'Firmware',
       'Firmware', 'Firmware', 'เฟิร์มแวร์', 'Oprogramowanie', 'Прошивка', 'Прошивка'),
    _t('Device', '设备', '裝置', 'デバイス', '기기', 'Appareil', 'Gerät',
       'Dispositivo', 'Dispositivo', 'อุปกรณ์', 'Urządzenie', 'Устройство', 'Пристрій'),
    _t('Model', '型号', '型號', 'モデル', '모델', 'Modèle', 'Modell',
       'Modelo', 'Modello', 'รุ่น', 'Model', 'Модель', 'Модель'),
    _t('Serial Number', '序列号', '序號', 'シリアル番号', '일련번호', 'N° de série', 'Seriennr.',
       'N.º de serie', 'N. di serie', 'หมายเลขเครื่อง', 'Nr seryjny', 'Серийный №', 'Серійний №'),
    _t('Wi-Fi MAC', 'Wi-Fi MAC', 'Wi-Fi MAC', 'Wi-Fi MAC', 'Wi-Fi MAC', 'Wi-Fi MAC', 'Wi-Fi MAC',
       'Wi-Fi MAC', 'Wi-Fi MAC', 'Wi-Fi MAC', 'Wi-Fi MAC', 'Wi-Fi MAC', 'Wi-Fi MAC'),
    _t('IP Address', 'IP 地址', 'IP 位址', 'IPアドレス', 'IP 주소', 'Adresse IP', 'IP-Adresse',
       'Dirección IP', 'Indirizzo IP', 'ที่อยู่ IP', 'Adres IP', 'IP-адрес', 'IP-адреса'),
    _t('Storage', '存储', '儲存空間', 'ストレージ', '저장공간', 'Stockage', 'Speicher',
       'Almacenamiento', 'Archiviazione', 'พื้นที่จัดเก็บ', 'Pamięć', 'Хранилище', 'Сховище'),
    _t('Capacity', '容量', '容量', '容量', '용량', 'Capacité', 'Kapazität',
       'Capacidad', 'Capacità', 'ความจุ', 'Pojemność', 'Ёмкость', 'Ємність'),
    _t('Available', '可用', '可用', '空き', '사용 가능', 'Disponible', 'Verfügbar',
       'Disponible', 'Disponibile', 'ว่าง', 'Dostępne', 'Доступно', 'Доступно'),
    _t('Theme', '主题', '主題', 'テーマ', '테마', 'Thème', 'Design',
       'Tema', 'Tema', 'ธีม', 'Motyw', 'Тема', 'Тема'),
    _t('Album Order', '专辑排序', '專輯排序', '並び順', '앨범 정렬', 'Tri', 'Sortierung',
       'Orden', 'Ordine', 'เรียงอัลบั้ม', 'Kolejność', 'Порядок', 'Порядок'),
    _t('Open Shanling Home', '打开山灵主页', '打開山靈主頁', 'Shanling ホームを開く', 'Shanling 홈 열기', 'Accueil Shanling', 'Shanling-Start öffnen',
       'Abrir Inicio Shanling', 'Apri Home Shanling', 'เปิดหน้าหลัก Shanling', 'Otwórz ekran Shanling', 'Открыть экран Shanling', 'Відкрити екран Shanling'),
    _t('Startup', '启动', '啟動', '起動', '시작', 'Démarrage', 'Start',
       'Inicio', 'Avvio', 'เริ่มต้น', 'Uruchamianie', 'Запуск', 'Запуск'),
    _t('Tools', '工具', '工具', 'ツール', '도구', 'Outils', 'Werkzeuge',
       'Herramientas', 'Strumenti', 'เครื่องมือ', 'Narzędzia', 'Инструменты', 'Інструменти'),
    _t('Shown on Home below the menu', '显示在主屏幕菜单下方', '顯示在主畫面選單下方', 'ホームのメニューの下に表示', '홈 메뉴 아래에 표시', "Affiché sous le menu d'accueil", 'Unter dem Menü auf dem Startbildschirm',
       'Se muestra bajo el menú de inicio', 'Mostrato sotto il menu in Home', 'แสดงใต้เมนูในหน้าหลัก', 'Widoczne pod menu na ekranie głównym', 'Под меню на главном экране', 'Під меню на головному екрані'),
    _t('A new mix the next time Home opens', '下次打开主屏幕时生成新的精选', '下次開啟主畫面時產生新的精選', '次にホームを開くと新しいミックス', '다음에 홈을 열면 새 믹스', "Un nouveau mix à la prochaine ouverture", 'Beim nächsten Öffnen ein neuer Mix',
       'Una mezcla nueva al abrir Inicio', 'Un nuovo mix alla prossima apertura', 'มิกซ์ใหม่เมื่อเปิดหน้าหลักครั้งถัดไป', 'Nowy miks przy następnym otwarciu', 'Новый микс при следующем открытии', 'Новий мікс при наступному відкритті'),
    _t('Scan the card for new music', '扫描存储卡中的新音乐', '掃描記憶卡中的新音樂', 'カードの新しい音楽をスキャン', '카드에서 새 음악 검색', 'Chercher de nouveaux titres sur la carte', 'Karte nach neuer Musik durchsuchen',
       'Buscar música nueva en la tarjeta', 'Cerca nuova musica sulla scheda', 'สแกนการ์ดหาเพลงใหม่', 'Szukaj nowej muzyki na karcie', 'Поиск новой музыки на карте', 'Пошук нової музики на картці'),
    _t('Albums and Cover Flow', '专辑和封面流', '專輯與封面流', 'アルバムとカバーフロー', '앨범 및 커버 플로우', 'Albums et Cover Flow', 'Alben und Cover Flow',
       'Álbumes y Cover Flow', 'Album e Cover Flow', 'อัลบั้มและ Cover Flow', 'Albumy i Cover Flow', 'Альбомы и Cover Flow', 'Альбоми та Cover Flow'),
    _t('Applies the next time Cassette Mode opens.', '下次打开磁带模式时生效。', '下次開啟錄音帶模式時生效。', '次回カセットモード起動時に反映', '다음에 카세트 모드를 열 때 적용됩니다.', "S'applique à la prochaine ouverture.", 'Gilt beim nächsten Öffnen.',
       'Se aplica la próxima vez que se abre.', 'Si applica alla prossima apertura.', 'มีผลเมื่อเปิดครั้งถัดไป', 'Zastosowane przy następnym otwarciu.', 'Применится при следующем открытии.', 'Застосується при наступному відкритті.'),
    _t('Off: the device starts on Shanling Home', '关闭：设备启动后进入山灵主页', '關閉：裝置啟動後進入山靈主頁', 'オフ：Shanling ホームで起動', '끔: Shanling 홈으로 시작', "Désactivé : démarre sur l'accueil Shanling", 'Aus: Start im Shanling-Start',
       'Desactivado: inicia en Inicio Shanling', 'Disattivo: avvio da Home Shanling', 'ปิด: เริ่มที่หน้าหลัก Shanling', 'Wył.: start z ekranu Shanling', 'Выкл.: запуск с экрана Shanling', 'Вимк.: запуск з екрана Shanling'),
    _t('Show, hide and reorder the menu', '显示、隐藏和排序菜单项', '顯示、隱藏及排序選單項目', 'メニュー項目の表示・非表示・並べ替え', '메뉴 항목 표시, 숨기기, 순서 변경', 'Afficher, masquer, réordonner le menu', 'Menü ein-, ausblenden, anordnen',
       'Mostrar, ocultar y ordenar el menú', 'Mostra, nascondi e riordina il menu', 'แสดง ซ่อน และเรียงเมนู', 'Pokaż, ukryj i uporządkuj menu', 'Показать, скрыть и упорядочить меню', 'Показати, сховати й упорядкувати меню'),
    _t('Items the menu does not show', '菜单中未显示的项目', '選單中未顯示的項目', 'メニューに表示されない項目', '메뉴에 표시되지 않는 항목', 'Éléments absents du menu', 'Einträge, die das Menü nicht zeigt',
       'Elementos que el menú no muestra', 'Voci non mostrate nel menu', 'รายการที่เมนูไม่แสดง', 'Pozycje niewidoczne w menu', 'Пункты, которых нет в меню', 'Пункти, яких немає в меню'),
    _t('Favorites', '我的最爱', '我的最愛', 'お気に入り', '즐겨찾기', 'Favoris', 'Favoriten',
       'Favoritos', 'Preferiti', 'รายการโปรด', 'Ulubione', 'Избранное', 'Вибране'),
    _t('Recently Added', '最近添加', '最近新增', '最近追加した曲', '최근 추가됨', 'Ajoutés récemment', 'Kürzlich hinzugefügt',
       'Añadidos recientemente', 'Aggiunti di recente', 'เพิ่มล่าสุด', 'Ostatnio dodane', 'Недавно добавленные', 'Нещодавно додані'),
    _t('Recently Played', '最近播放', '最近播放', '最近再生した曲', '최근 재생', 'Lus récemment', 'Zuletzt gespielt',
       'Reproducido hace poco', 'Riprodotti di recente', 'เล่นล่าสุด', 'Ostatnio odtwarzane', 'Недавно слушали', 'Нещодавно відтворені'),
    # Settings > Home Screen > the Recently Played shelf's switch (patch/recent.c). Its own wording: the menu item's text above is too
    # wide for the switch row in Spanish and Ukrainian, and the shelf shows albums
    _t('Recent Albums', '最近专辑', '最近專輯', '最近のアルバム', '최근 앨범', 'Albums récents', 'Letzte Alben',
       'Álbumes recientes', 'Album recenti', 'อัลบั้มล่าสุด', 'Ostatnie albumy', 'Недавние альбомы', 'Недавні альбоми'),
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
    _t('Top Results', '热门结果', '熱門結果', '上位の結果', '상위 결과', 'Meilleurs résultats', 'Top-Ergebnisse',
       'Mejores resultados', 'Risultati migliori', 'ผลลัพธ์ยอดนิยม', 'Najlepsze wyniki', 'Лучшие результаты', 'Найкращі результати'),
    _t('Song', '歌曲', '歌曲', '曲', '노래', 'Titre', 'Titel',
       'Canción', 'Brano', 'เพลง', 'Utwór', 'Песня', 'Пісня'),
    _t('Playlist', '歌单', '歌單', 'プレイリスト', '플레이리스트', 'Playlist', 'Playlist',
       'Lista', 'Playlist', 'เพลย์ลิสต์', 'Playlista', 'Плейлист', 'Плейлист'),
    _t('No Results', '无结果', '無結果', '結果なし', '결과 없음', 'Aucun résultat', 'Keine Ergebnisse',
       'Sin resultados', 'Nessun risultato', 'ไม่พบผลลัพธ์', 'Brak wyników', 'Нет результатов', 'Немає результатів'),
    _t('No albums', '没有专辑', '沒有專輯', 'アルバムがありません', '앨범 없음', 'Aucun album', 'Keine Alben',
       'Sin álbumes', 'Nessun album', 'ไม่มีอัลบั้ม', 'Brak albumów', 'Нет альбомов', 'Немає альбомів'),
    _t('No artists', '没有艺术家', '沒有藝術家', 'アーティストがありません', '아티스트 없음', 'Aucun artiste', 'Keine Künstler',
       'Sin artistas', 'Nessun artista', 'ไม่มีศิลปิน', 'Brak wykonawców', 'Нет исполнителей', 'Немає виконавців'),
    _t('Music', '音乐', '音樂', 'ミュージック', '음악', 'Musique', 'Musik',
       'Música', 'Musica', 'เพลง', 'Muzyka', 'Музыка', 'Музика'),
    # the Settings > Cover Flow sub-page (landscape switch; sort order, valued Artist or Album: "Album" is the stock key 'album')
    _t('Landscape', '横屏', '橫向', '横向き', '가로 모드', 'Paysage', 'Querformat',
       'Horizontal', 'Orizzontale', 'แนวนอน', 'Poziomo', 'Горизонтально', 'Горизонтально'),
    _t('Artist', '歌手', '歌手', 'アーティスト', '아티스트', 'Artiste', 'Künstler',
       'Artista', 'Artista', 'ศิลปิน', 'Wykonawca', 'Исполнитель', 'Виконавець'),
    # Settings > Library > Rebuild Covers: the row, and the message of the stock confirm dialog (a centred white 20 px label
    # that wraps in 260 x 80 px: at most three lines, test/pod/i18n.py)
    _t('Rebuild Covers', '重建封面', '重建封面', 'カバーを再作成', '커버 다시 만들기', 'Recréer les pochettes', 'Cover neu erstellen',
       'Recrear carátulas', 'Ricrea copertine', 'สร้างปกใหม่', 'Odbuduj okładki', 'Пересоздать обложки', 'Оновити обкладинки'),
    _t('Rebuild all covers? This may take a few minutes.', '重建所有封面？这可能需要几分钟。', '重建所有封面？這可能需要幾分鐘。',
       'すべてのカバーを再作成しますか？数分かかる場合があります。', '모든 커버를 다시 만들까요? 몇 분 걸릴 수 있습니다.',
       'Recréer toutes les pochettes ? Cela peut prendre quelques minutes.', 'Alle Cover neu erstellen? Das kann einige Minuten dauern.',
       '¿Recrear todas las carátulas? Puede tardar unos minutos.', 'Ricreare tutte le copertine? Potrebbe richiedere alcuni minuti.',
       'สร้างปกทั้งหมดใหม่หรือไม่ อาจใช้เวลาสองสามนาที', 'Odbudować wszystkie okładki? Może to potrwać kilka minut.',
       'Пересоздать все обложки? Это может занять несколько минут.', 'Оновити всі обкладинки? Це може тривати кілька хвилин.'),
    # the track count of the album page's meta line: the payload chooses the key by n == 1 and puts the number where %d is;
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
    # the iPod page's Settings list (patch/ipod.c): the labels and the values that cycle (Shuffle: Off / Songs; Repeat: Off / One / All; its last row is the shared Settings key)
    _t('Repeat', '重复', '重複', 'リピート', '반복', 'Répéter', 'Wiederholen',
       'Repetir', 'Ripeti', 'เล่นซ้ำ', 'Powtarzaj', 'Повтор', 'Повтор'),
    _t('Off', '关', '關', 'オフ', '끔', 'Désactivé', 'Aus',
       'Desactivado', 'Disattivato', 'ปิด', 'Wył.', 'Выкл.', 'Вимк.'),
    _t('One', '单曲', '單曲', '1曲', '한 곡', 'Un titre', 'Einzeln',
       'Una', 'Uno', 'เพลงเดียว', 'Jeden', 'Один', 'Один'),
    _t('All', '全部', '全部', 'すべて', '전체', 'Tous', 'Alle',
       'Todo', 'Tutti', 'ทั้งหมด', 'Wszystkie', 'Все', 'Усі'),
    # Podcast search (patch/podcasts.c, docs/modules/podcasts.md "Search"): the Settings row and its note, the search page's states, the preview's Subscribe pill
    _t('Podcast Search', '播客搜索', '播客搜尋', 'ポッドキャスト検索', '팟캐스트 검색', 'Recherche', 'Podcast-Suche',
       'Buscar pódcast', 'Cerca podcast', 'ค้นหาพอดแคสต์', 'Szukaj podcastów', 'Поиск подкастов', 'Пошук подкастів'),
    _t('Search words are sent to Apple.', '搜索词会发送给 Apple。', '搜尋詞會傳送給 Apple。', '検索語は Apple に送信されます。', '검색어는 Apple로 전송됩니다.', 'Les mots recherchés sont envoyés à Apple.',
       'Suchbegriffe werden an Apple gesendet.', 'Los términos se envían a Apple.', 'Le parole cercate vanno ad Apple.', 'คำค้นหาจะถูกส่งไปยัง Apple', 'Szukane słowa trafiają do Apple.',
       'Слова запроса отправляются в Apple.', 'Слова запиту надсилаються до Apple.'),
    _t('Searching…', '正在搜索…', '正在搜尋…', '検索中…', '검색 중…', 'Recherche…', 'Suche läuft…',
       'Buscando…', 'Ricerca in corso…', 'กำลังค้นหา…', 'Szukanie…', 'Поиск…', 'Пошук…'),
    _t('Loading…', '正在加载…', '正在載入…', '読み込み中…', '불러오는 중…', 'Chargement…', 'Wird geladen…',
       'Cargando…', 'Caricamento…', 'กำลังโหลด…', 'Wczytywanie…', 'Загрузка…', 'Завантаження…'),
    _t('No results', '无结果', '無結果', '結果なし', '결과 없음', 'Aucun résultat', 'Keine Ergebnisse',
       'Sin resultados', 'Nessun risultato', 'ไม่พบผลลัพธ์', 'Brak wyników', 'Нет результатов', 'Немає результатів'),
    _t('Not available', '不可用', '無法使用', '利用できません', '사용할 수 없음', 'Indisponible', 'Nicht verfügbar',
       'No disponible', 'Non disponibile', 'ไม่พร้อมใช้งาน', 'Niedostępny', 'Недоступно', 'Недоступно'),
    _t('Subscribe', '订阅', '訂閱', '登録', '구독', "S'abonner", 'Abonnieren',
       'Suscribirse', 'Iscriviti', 'ติดตาม', 'Subskrybuj', 'Подписаться', 'Підписатися'),
    _t("Can't subscribe", '无法订阅', '無法訂閱', '登録できません', '구독할 수 없음', 'Abonnement impossible', 'Abonnieren nicht möglich',
       'No se puede suscribir', 'Impossibile iscriversi', 'ติดตามไม่ได้', 'Nie można subskrybować', 'Не удалось подписаться', 'Не вдалося підписатися'),
    # Podcasts (patch/podcasts.c, docs/modules/podcasts.md): the Extras item and the page's title, the two empty lines, the counts, the grey line of an episode
    _t('Podcasts', '播客', '播客', 'ポッドキャスト', '팟캐스트', 'Podcasts', 'Podcasts',
       'Pódcast', 'Podcast', 'พอดแคสต์', 'Podcasty', 'Подкасты', 'Подкасти'),
    _t('No podcasts. Copy a folder for each show into Podcasts on the card, or put subscriptions.txt there and choose Import from Card in the menu at the top right.',
       '没有播客。请在存储卡的 Podcasts 文件夹中为每个节目放一个文件夹，或把 subscriptions.txt 放在那里，然后在右上角的菜单中选择“从存储卡导入”。',
       '沒有播客。請在記憶卡的 Podcasts 資料夾中為每個節目放一個資料夾，或把 subscriptions.txt 放在那裡，然後在右上角的選單中選擇「從記憶卡匯入」。',
       'ポッドキャストがありません。カードの Podcasts フォルダに番組ごとのフォルダをコピーするか、subscriptions.txt を置いて、右上のメニューで「カードから読み込む」を選んでください。',
       '팟캐스트가 없습니다. 카드의 Podcasts 폴더에 프로그램마다 폴더를 복사하거나 subscriptions.txt를 넣고 오른쪽 위 메뉴에서 "카드에서 가져오기"를 선택하세요.',
       'Aucun podcast. Copiez un dossier par émission dans Podcasts sur la carte, ou placez-y subscriptions.txt et choisissez Importer depuis la carte dans le menu en haut à droite.',
       'Keine Podcasts. Kopiere für jede Sendung einen Ordner in Podcasts auf der Karte oder lege dort subscriptions.txt ab und wähle oben rechts im Menü Von Karte importieren.',
       'Sin pódcast. Copia una carpeta por programa en Podcasts de la tarjeta, o pon allí subscriptions.txt y elige Importar desde la tarjeta en el menú de arriba a la derecha.',
       'Nessun podcast. Copia una cartella per ogni programma in Podcasts sulla scheda, oppure mettici subscriptions.txt e scegli Importa dalla scheda nel menu in alto a destra.',
       'ไม่มีพอดแคสต์ คัดลอกโฟลเดอร์ของแต่ละรายการไปที่ Podcasts บนการ์ด หรือวาง subscriptions.txt ไว้ที่นั่น แล้วเลือกนำเข้าจากการ์ดในเมนูที่มุมขวาบน',
       'Brak podcastów. Skopiuj folder dla każdego programu do Podcasts na karcie albo połóż tam subscriptions.txt i wybierz Importuj z karty w menu w prawym górnym rogu.',
       'Нет подкастов. Скопируйте по папке на каждое шоу в Podcasts на карте или положите туда subscriptions.txt и выберите «Импорт с карты» в меню вверху справа.',
       'Немає подкастів. Скопіюйте по теці для кожного шоу в Podcasts на картці або покладіть туди subscriptions.txt і виберіть «Імпорт з картки» в меню вгорі праворуч.'),
    # The Shows page (patch/podcasts.c, docs/modules/podcasts.md "The Shows page"): the two section headers, the refresh line's word and its progress, the menu's row, the Show page's empty hint
    _t('Continue Listening', '继续收听', '繼續收聽', '続きを聴く', '이어 듣기', 'Reprendre la lecture', 'Weiterhören', 'Seguir escuchando', 'Continua ad ascoltare', 'ฟังต่อ', 'Kontynuuj słuchanie', 'Продолжить слушать', 'Продовжити слухати'),
    _t('Shows', '节目', '節目', '番組', '프로그램', 'Émissions', 'Sendungen', 'Programas', 'Programmi', 'รายการ', 'Programy', 'Шоу', 'Шоу'),
    _t('Refresh', '刷新', '更新', '更新', '새로고침', 'Actualiser', 'Aktualisieren', 'Actualizar', 'Aggiorna', 'รีเฟรช', 'Odśwież', 'Обновить', 'Оновити'),
    _t('Refreshing %d/%d…', '正在刷新 %d/%d…', '正在更新 %d/%d…', '更新中 %d/%d…', '새로고침 중 %d/%d…', 'Actualisation %d/%d…', 'Aktualisiere %d/%d …', 'Actualizando %d/%d…', 'Aggiornamento %d/%d…', 'กำลังรีเฟรช %d/%d…',
       'Odświeżanie %d/%d…', 'Обновление %d/%d…', 'Оновлення %d/%d…'),
    _t('Import from Card', '从存储卡导入', '從記憶卡匯入', 'カードから読み込む', '카드에서 가져오기', 'Importer depuis la carte', 'Von Karte importieren', 'Importar desde la tarjeta', 'Importa dalla scheda', 'นำเข้าจากการ์ด',
       'Importuj z karty', 'Импорт с карты', 'Імпорт з картки'),
    _t('No episodes yet. Choose Refresh Feed in the menu at the top right.', '暂无节目。请在右上角的菜单中选择“刷新订阅源”。', '暫無節目。請在右上角的選單中選擇「更新訂閱源」。', 'エピソードはまだありません。右上のメニューで「フィードを更新」を選んでください。',
       '아직 에피소드가 없습니다. 오른쪽 위 메뉴에서 "피드 새로고침"을 선택하세요.', "Aucun épisode pour l'instant. Choisissez Actualiser dans le menu en haut à droite.", 'Noch keine Folgen. Wähle oben rechts im Menü Aktualisieren.',
       'Aún no hay episodios. Elige Actualizar en el menú de arriba a la derecha.', 'Ancora nessun episodio. Scegli Aggiorna nel menu in alto a destra.', 'ยังไม่มีตอน เลือกรีเฟรชฟีดในเมนูที่มุมขวาบน',
       'Brak odcinków. Wybierz Odśwież w menu w prawym górnym rogu.', 'Эпизодов пока нет. Выберите «Обновить» в меню вверху справа.', 'Епізодів поки немає. Виберіть «Оновити» в меню вгорі праворуч.'),
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
    _t('Never refreshed', '从未刷新', '從未更新', '未更新', '새로고침 안 함', 'Jamais actualisé', 'Nie aktualisiert', 'Nunca actualizado', 'Mai aggiornato', 'ยังไม่เคยรีเฟรช', 'Nie odświeżano', 'Не обновлялось', 'Не оновлювалось'),
    _t('%d new', '%d 个新节目', '%d 個新節目', '新着 %d 件', '새 에피소드 %d개', '%d nouveaux', '%d neue', '%d nuevos', '%d nuovi', 'ใหม่ %d', '%d nowe', 'Новых: %d', 'Нових: %d'),
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
    _t('No downloaded episodes', '没有已下载的节目', '沒有已下載的節目', 'ダウンロード済みのエピソードがありません', '다운로드한 에피소드가 없습니다', 'Aucun épisode téléchargé', 'Keine geladenen Folgen',
       'Sin episodios descargados', 'Nessun episodio scaricato', 'ไม่มีตอนที่ดาวน์โหลด', 'Brak pobranych odcinków', 'Нет загруженных выпусков', 'Немає завантажених випусків'),
    _t('%d episode', '%d 个节目', '%d 個節目', '%d エピソード', '에피소드 %d개', '%d épisode', '%d Folge',
       '%d episodio', '%d episodio', '%d ตอน', 'Odcinki: %d', 'Выпусков: %d', 'Випусків: %d'),
    _t('%d episodes', '%d 个节目', '%d 個節目', '%d エピソード', '에피소드 %d개', '%d épisodes', '%d Folgen',
       '%d episodios', '%d episodi', '%d ตอน', 'Odcinki: %d', 'Выпусков: %d', 'Випусків: %d'),
    # The Show page (patch/podcasts.c, docs/modules/podcasts.md "The Show page"): the header's pill and list title, the two bottom sheets, the pills' labels
    _t('Latest Episode', '最新一集', '最新一集', '最新エピソード', '최신 에피소드', 'Dernier épisode', 'Neueste Folge', 'Último episodio', 'Ultimo episodio', 'ตอนล่าสุด', 'Najnowszy odcinek', 'Последний выпуск', 'Останній випуск'),
    _t('Episodes', '单集', '單集', 'エピソード', '에피소드', 'Épisodes', 'Folgen', 'Episodios', 'Episodi', 'ตอน', 'Odcinki', 'Выпуски', 'Випуски'),
    _t('Playback Speed', '播放速度', '播放速度', '再生速度', '재생 속도', 'Vitesse de lecture', 'Wiedergabetempo', 'Velocidad', 'Velocità di riproduzione', 'ความเร็วในการเล่น', 'Prędkość odtwarzania', 'Скорость', 'Швидкість відтворення'),
    _t('Refresh Feed', '刷新订阅源', '更新訂閱源', 'フィードを更新', '피드 새로고침', 'Actualiser', 'Aktualisieren', 'Actualizar', 'Aggiorna', 'รีเฟรชฟีด', 'Odśwież', 'Обновить', 'Оновити'),
    _t('Select Episodes', '选择节目', '選擇節目', 'エピソードを選択', '에피소드 선택', 'Sélectionner des épisodes', 'Folgen auswählen', 'Seleccionar episodios', 'Seleziona episodi', 'เลือกตอน', 'Wybierz odcinki', 'Выбрать выпуски', 'Вибрати випуски'),
    _t('Mark All as Played', '全部标为已播放', '全部標為已播放', 'すべて再生済みにする', '모두 재생함으로 표시', 'Tout marquer comme lu', 'Alle als gehört markieren', 'Marcar todo como reproducido', 'Segna tutto come riprodotto',
       'ทำเครื่องหมายว่าเล่นแล้วทั้งหมด', 'Wszystkie jako odtworzone', 'Все как прослушанные', 'Усі як прослухані'),
    _t('Unsubscribe', '取消订阅', '取消訂閱', '登録解除', '구독 취소', 'Se désabonner', 'Abo beenden', 'Cancelar suscripción', 'Annulla iscrizione', 'เลิกติดตาม', 'Anuluj subskrypcję', 'Отписаться', 'Скасувати підписку'),
    _t('Unsubscribe from this show?', '取消订阅此节目？', '取消訂閱此節目？', 'この番組の登録を解除しますか？', '이 프로그램 구독을 취소할까요?', 'Se désabonner de ce podcast ?', 'Diesen Podcast nicht mehr abonnieren?',
       '¿Cancelar la suscripción a este podcast?', "Annullare l'iscrizione a questo podcast?", 'เลิกติดตามพอดแคสต์นี้หรือไม่?', 'Anulować subskrypcję tego podcastu?', 'Отписаться от этого подкаста?', 'Скасувати підписку на цей подкаст?'),
    _t('Download', '下载', '下載', 'ダウンロード', '다운로드', 'Télécharger', 'Laden', 'Descargar', 'Scarica', 'ดาวน์โหลด', 'Pobierz', 'Загрузить', 'Завантажити'),
    _t('Remove Download', '移除下载', '移除下載', 'ダウンロードを削除', '다운로드 제거', 'Supprimer le téléchargement', 'Download entfernen', 'Quitar descarga', 'Rimuovi download', 'ลบการดาวน์โหลด', 'Usuń pobrany plik', 'Удалить загрузку', 'Видалити завантаження'),
    _t('Mark as Played', '标为已播放', '標為已播放', '再生済みにする', '재생함으로 표시', 'Marquer comme lu', 'Als gehört markieren', 'Marcar como reproducido', 'Segna come riprodotto', 'ทำเครื่องหมายว่าเล่นแล้ว', 'Oznacz jako odtworzone', 'Отметить как прослушанное', 'Позначити як прослухане'),
    _t('Mark as Unplayed', '标为未播放', '標為未播放', '未再生にする', '재생 안 함으로 표시', 'Marquer comme non lu', 'Als ungehört markieren', 'Marcar como no reproducido', 'Segna come non riprodotto', 'ทำเครื่องหมายว่ายังไม่เล่น', 'Oznacz jako nieodtworzone', 'Отметить как непрослушанное', 'Позначити як непрослухане'),
    _t('Retry', '重试', '重試', '再試行', '다시 시도', 'Réessayer', 'Erneut', 'Reintentar', 'Riprova', 'ลองใหม่', 'Ponów', 'Повторить', 'Повторити'),
    _t('%dm', '%d分钟', '%d分鐘', '%d分', '%d분', '%d min', '%d Min.', '%d min', '%d min', '%d นาที', '%d min', '%d мин', '%d хв'),   # the pill's length: short, no "left"
    _t('%dm left', '剩余%d分钟', '剩餘%d分鐘', '残り%d分', '%d분 남음', 'Reste %d min', 'Noch %d Min.', 'Quedan %d min', '%d min rimasti', 'เหลือ %d นาที', 'Zostało %d min', 'Ещё %d мин', 'Ще %d хв'),
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
    # Network Probe (Settings > Developer; patch/probe.c)
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
    # Settings > Keyboards (iOS style: English always on, Chinese (Pinyin) a switch; patch/keyboard.c)
    _t('Keyboards', '键盘', '鍵盤', 'キーボード', '키보드', 'Claviers', 'Tastaturen',
       'Teclados', 'Tastiere', 'แป้นพิมพ์', 'Klawiatury', 'Клавиатуры', 'Клавіатури'),
    _t('English', '英语', '英語', '英語', '영어', 'Anglais', 'Englisch',
       'Inglés', 'Inglese', 'อังกฤษ', 'Angielski', 'Английский', 'Англійська'),
    _t('Chinese (Pinyin)', '中文拼音', '中文拼音', '中国語（ピンイン）', '중국어(병음)', 'Chinois (pinyin)', 'Chinesisch (Pinyin)',
       'Chino (pinyin)', 'Cinese (pinyin)', 'จีน (พินอิน)', 'Chiński (pinyin)', 'Пиньинь (кит.)', 'Китайська (піньїнь)'),
    # The on-screen keyboard (patch/keyboard.c; the Developer row, the page's title and the keys' labels)
    _t('Keyboard', '键盘', '鍵盤', 'キーボード', '키보드', 'Clavier', 'Tastatur',
       'Teclado', 'Tastiera', 'แป้นพิมพ์', 'Klawiatura', 'Клавиатура', 'Клавіатура'),
    _t('space', '空格', '空格', 'スペース', '스페이스', 'espace', 'Leertaste',
       'espacio', 'spazio', 'เว้นวรรค', 'spacja', 'пробел', 'пробіл'),
    _t('Search', '搜索', '搜尋', '検索', '검색', 'Chercher', 'Suchen',
       'Buscar', 'Cerca', 'ค้นหา', 'Szukaj', 'Поиск', 'Пошук'),
    _t('Done', '完成', '完成', '完了', '완료', 'OK', 'Fertig',
       'Hecho', 'Fine', 'เสร็จ', 'Gotowe', 'Готово', 'Готово'),
    _t('Type here', '在此输入', '在此輸入', 'ここに入力', '여기에 입력', 'Saisir ici', 'Hier tippen',
       'Escribe aquí', 'Digita qui', 'พิมพ์ที่นี่', 'Wpisz tutaj', 'Введите здесь', 'Введіть тут'),
    # Now Playing's More menu (patch/playmore.c): the row that opens the second page (and that page's back header), the short
    # Playback speed label (stock: "Multiple Speed", wider than the room before the four speed badges) and the 14 px note under it
    _t('More', '更多', '更多', 'その他', '더 보기', 'Plus', 'Mehr',
       'Más', 'Altro', 'เพิ่มเติม', 'Więcej', 'Ещё', 'Ще'),
    _t('Speed', '倍速', '倍速', '再生速度', '재생 속도', 'Vitesse', 'Tempo',
       'Velocidad', 'Velocità', 'ความเร็ว', 'Prędkość', 'Скорость', 'Швидкість'),
    # Now Playing's More sheet: the row that opens the landscape cassette page (patch/tape.c, docs/modules/tape.md); the page's own name is the same text
    _t('Cassette Mode', '磁带模式', '錄音帶模式', 'カセットモード', '카세트 모드', 'Mode cassette', 'Kassettenmodus',
       'Modo casete', 'Modalità cassetta', 'โหมดเทป', 'Tryb kasety', 'Режим кассеты', 'Режим касети'),
    # Settings > Now Playing > Theme: the picker's title and its three values
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
    # Settings > Home Screen switch row ("Daily Mix": the card breaks it at its first space into two lines, a word with no space is one line on the bottom one),
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
    # The section headers of the Extras page and Settings > Extras (pod_pages.EXTRAS_GROUPS): Play is the key above. The stock tables have no key for these
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
DATE_KEYS = _MONTH_KEYS + (', %d', '%dm ago', '%dh ago', '%dd ago', 'Refreshing %d/%d…')   # keys with a %d that do not start with it (the tables test, test/pod/i18n.py)
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
