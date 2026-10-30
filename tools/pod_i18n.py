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
       'Ajustes del sistema', 'Impostazioni di sistema', 'การตั้งค่าระบบ', 'Ustawienia systemowe', 'Системные настройки', 'Системні налаштування'),
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
    # Now Playing's More menu (patch/playmore.c): the row that opens the second page (and that page's back header), the short
    # Playback speed label (stock: "Multiple Speed", wider than the room before the four speed badges) and the 14 px note under it
    _t('More', '更多', '更多', 'その他', '더 보기', 'Plus', 'Mehr',
       'Más', 'Altro', 'เพิ่มเติม', 'Więcej', 'Ещё', 'Ще'),
    _t('Speed', '倍速', '倍速', '再生速度', '재생 속도', 'Vitesse', 'Tempo',
       'Velocidad', 'Velocità', 'ความเร็ว', 'Prędkość', 'Скорость', 'Швидкість'),
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
DPAGE_KEYS = ('Updated today', 'Updated yesterday', 'Updated %s', 'Play', 'Songs you love and some to rediscover, made fresh every day.')   # the Daily Mix page's keys
DAILY_KEYS =('Made for You', 'Daily Mix', 'Regenerate Daily Mix', '%s and more', '%s, %s')     # the card's keys (tools/pod_dailymix.py TEXT)

KEYS = sorted(TEXT)


def english(key):
    """The English text a key stands for (our keys are their own English; stock keys come from STOCK)."""
    return TEXT[key]['en_US'] if key in TEXT else STOCK[key]


BRANDS = ('M1+ Music', 'Tidal')     # shown as they are, no key


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
