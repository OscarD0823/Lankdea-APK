"""Traducciones compactas de la interfaz principal.

El español y el inglés cubren todos los textos registrados. Los otros idiomas
traducen la navegación esencial y usan inglés como fallback, igual que la
interfaz multilingüe de referencia del proyecto hermano.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    short: str
    name: str


LANGUAGES = (
    Language("es", "ES", "Español"),
    Language("en", "EN", "English"),
    Language("pt", "PT", "Português"),
    Language("fr", "FR", "Français"),
    Language("de", "DE", "Deutsch"),
    Language("it", "IT", "Italiano"),
    Language("pl", "PL", "Polski"),
    Language("tr", "TR", "Türkçe"),
    Language("ru", "RU", "Русский"),
    Language("ja", "JA", "日本語"),
    Language("ko", "KO", "한국어"),
    Language("zh", "ZH", "简体中文"),
)

_BY_CODE = {language.code: language for language in LANGUAGES}


def _row(es: str, en: str, **translations: str) -> dict[str, str]:
    return {"es": es, "en": en, **translations}


TEXT = {
    "personal_vault": _row("Cofre cifrado personal", "Personal encrypted vault", pt="Cofre pessoal cifrado", fr="Coffre personnel chiffré", de="Persönlicher verschlüsselter Tresor", it="Cassaforte personale cifrata", pl="Osobisty szyfrowany sejf", tr="Kişisel şifreli kasa", ru="Личный зашифрованный сейф", ja="個人用暗号化保管庫", ko="개인 암호화 금고", zh="个人加密保险库"),
    "search_short": _row("Buscar en el cofre", "Search your vault", pt="Buscar no cofre", fr="Rechercher dans le coffre", de="Tresor durchsuchen", it="Cerca nella cassaforte", pl="Szukaj w sejfie", tr="Kasada ara", ru="Поиск в сейфе", ja="保管庫を検索", ko="금고 검색", zh="搜索保险库"),
    "status_summary": _row("{count} registros  •  Revisión {revision}", "{count} records  •  Revision {revision}"),
    "add_file": _row("Guardar archivo", "Store file", pt="Guardar arquivo", fr="Ajouter un fichier", de="Datei speichern", it="Salva file", pl="Zapisz plik", tr="Dosya kaydet", ru="Сохранить файл", ja="ファイルを保存", ko="파일 저장", zh="保存文件"),
    "export_file": _row("Exportar archivo", "Export file", pt="Exportar arquivo", fr="Exporter le fichier", de="Datei exportieren", it="Esporta file", pl="Eksportuj plik", tr="Dosyayı dışa aktar", ru="Экспорт файла", ja="ファイルを出力", ko="파일 내보내기", zh="导出文件"),
    "save": _row("Guardar", "Save", pt="Salvar", fr="Enregistrer", de="Speichern", it="Salva", pl="Zapisz", tr="Kaydet", ru="Сохранить", ja="保存", ko="저장", zh="保存"),
    "cancel": _row("Cancelar", "Cancel", pt="Cancelar", fr="Annuler", de="Abbrechen", it="Annulla", pl="Anuluj", tr="İptal", ru="Отмена", ja="キャンセル", ko="취소", zh="取消"),
    "select": _row("Seleccionar", "Select"),
    "filename": _row("Nombre del archivo", "File name"),
    "title": _row("Título", "Title"),
    "error": _row("Error", "Error"),
    "encrypting": _row("Cifrando archivo…", "Encrypting file…"),
    "decrypting": _row("Exportando copia legible…", "Exporting readable copy…"),
    "exported": _row("Archivo creado en:", "File created at:"),
    "unlock_file_action": _row("Abre de nuevo el cofre para continuar con el archivo elegido.", "Unlock again to continue with the selected file."),
    "plaintext_warning": _row("La copia exportada NO estará cifrada. Cualquier persona o app que tenga acceso a esa copia podrá leerla. El original dentro del cofre seguirá cifrado.", "The exported copy will NOT be encrypted. Anyone or any app with access to that copy can read it. The vault's original remains encrypted."),
    "restore_backup": _row("Restaurar respaldo", "Restore backup"),
    "backup_password": _row("Contraseña del respaldo", "Backup password"),
    "backup_password_help": _row("Usa la contraseña con que se creó el respaldo. Deja vacío para usar la del cofre abierto. Los registros se combinan; no se borra el cofre actual.", "Use the password used to create the backup. Leave blank to use the open vault's password. Records are merged; the current vault is not erased."),
    "restore_android_hint": _row("Restaura este respaldo completo desde la app de PC y después sincroniza el celular. No se ha importado ni modificado ningún dato.", "Restore this complete backup on the PC app, then sync your phone. No data has been imported or changed."),
    "identity_verified": _row("IDENTIDAD VERIFICADA  //  NÚCLEO EN LÍNEA", "IDENTITY VERIFIED  //  CORE ONLINE"),
    "welcome_message": _row("Bienvenido. El cofre está abierto. Tus notas, claves y archivos están listos; tú tienes el control.", "Welcome. The vault is open. Your notes, passwords and files are ready; you are in control."),
    "unlock_help": _row("Escribe tu frase maestra. Si activaste Authenticator, el código será el segundo paso.", "Enter your master phrase. If Authenticator is enabled, its code is the second step."),
    "create_help": _row("Elige una frase maestra de al menos 12 caracteres. Sin ella no se podrán recuperar tus datos. Authenticator no la reemplaza.", "Choose a master phrase of at least 12 characters. Without it your data cannot be recovered. Authenticator does not replace it."),
    "checking": _row("Comprobando…", "Checking…"),
    "empty_hint": _row("Guarda una nota, contraseña, foto o documento.", "Store a note, password, photo or document."),
    "service": _row("Servicio / app", "Service / app"),
    "username": _row("Usuario / correo", "Username / email"),
    "password": _row("Contraseña", "Password"),
    "optional_notes": _row("Notas opcionales", "Optional notes"),
    "show_password": _row("Mostrar contraseña", "Show password"),
    "hide_password": _row("Ocultar contraseña", "Hide password"),
    "save_credential": _row("Guardar credencial", "Save credential"),
    "edit_credential": _row("Editar credencial", "Edit credential"),
    "note_content": _row("Contenido de la nota", "Note content"),
    "save_note": _row("Guardar nota", "Save note"),
    "edit_note": _row("Editar nota", "Edit note"),
    "language": _row("Idioma", "Language", pt="Idioma", fr="Langue", de="Sprache", it="Lingua", pl="Język", tr="Dil", ru="Язык", ja="言語", ko="언어", zh="语言"),
    "encrypted_vault": _row("RELICARIO CIFRADO  //  BLOQUEADO", "ENCRYPTED VAULT  //  LOCKED", pt="COFRE CIFRADO  //  BLOQUEADO", fr="COFFRE CHIFFRÉ  //  VERROUILLÉ", de="VERSCHLÜSSELTER TRESOR  //  GESPERRT", it="CASSAFORTE CIFRATA  //  BLOCCATA", pl="SZYFROWANY SEJF  //  ZABLOKOWANY", tr="ŞİFRELİ KASA  //  KİLİTLİ", ru="ЗАШИФРОВАННЫЙ СЕЙФ  //  ЗАКРЫТ", ja="暗号化保管庫  //  ロック中", ko="암호화 금고  //  잠김", zh="加密保险库  //  已锁定"),
    "secure_access": _row("LANKDEA  //  ACCESO SEGURO", "LANKDEA  //  SECURE ACCESS", pt="LANKDEA  //  ACESSO SEGURO", fr="LANKDEA  //  ACCÈS SÉCURISÉ", de="LANKDEA  //  SICHERER ZUGANG", it="LANKDEA  //  ACCESSO SICURO", pl="LANKDEA  //  BEZPIECZNY DOSTĘP", tr="LANKDEA  //  GÜVENLİ ERİŞİM", ru="LANKDEA  //  БЕЗОПАСНЫЙ ДОСТУП", ja="LANKDEA  //  セキュアアクセス", ko="LANKDEA  //  보안 액세스", zh="LANKDEA  //  安全访问"),
    "master_password": _row("Contraseña maestra", "Master password", pt="Senha mestra", fr="Mot de passe maître", de="Master-Passwort", it="Password principale", pl="Hasło główne", tr="Ana parola", ru="Мастер-пароль", ja="マスターパスワード", ko="마스터 비밀번호", zh="主密码"),
    "new_master_password": _row("Nueva contraseña maestra", "New master password", pt="Nova senha mestra", fr="Nouveau mot de passe maître", de="Neues Master-Passwort", it="Nuova password principale", pl="Nowe hasło główne", tr="Yeni ana parola", ru="Новый мастер-пароль", ja="新しいマスターパスワード", ko="새 마스터 비밀번호", zh="新主密码"),
    "repeat_password": _row("Repite la contraseña", "Repeat password", pt="Repita a senha", fr="Répétez le mot de passe", de="Passwort wiederholen", it="Ripeti la password", pl="Powtórz hasło", tr="Parolayı tekrarla", ru="Повторите пароль", ja="パスワードを再入力", ko="비밀번호 다시 입력", zh="重复密码"),
    "verify_open": _row("Verificar identidad y abrir", "Verify identity and open", pt="Verificar identidade e abrir", fr="Vérifier et ouvrir", de="Identität prüfen und öffnen", it="Verifica e apri", pl="Sprawdź i otwórz", tr="Kimliği doğrula ve aç", ru="Проверить и открыть", ja="本人確認して開く", ko="신원 확인 후 열기", zh="验证身份并打开"),
    "create_vault": _row("Crear cofre cifrado", "Create encrypted vault", pt="Criar cofre cifrado", fr="Créer le coffre chiffré", de="Verschlüsselten Tresor erstellen", it="Crea cassaforte cifrata", pl="Utwórz szyfrowany sejf", tr="Şifreli kasa oluştur", ru="Создать зашифрованный сейф", ja="暗号化保管庫を作成", ko="암호화 금고 만들기", zh="创建加密保险库"),
    "updates_help": _row("Actualizaciones y ayuda", "Updates and help", pt="Atualizações e ajuda", fr="Mises à jour et aide", de="Updates und Hilfe", it="Aggiornamenti e aiuto", pl="Aktualizacje i pomoc", tr="Güncellemeler ve yardım", ru="Обновления и помощь", ja="更新とヘルプ", ko="업데이트 및 도움말", zh="更新与帮助"),
    "new_credential": _row("Nueva credencial", "New credential", pt="Nova credencial", fr="Nouvel identifiant", de="Neue Zugangsdaten", it="Nuova credenziale", pl="Nowe dane logowania", tr="Yeni kimlik bilgisi", ru="Новые учетные данные", ja="新しい認証情報", ko="새 자격 증명", zh="新凭据"),
    "new_note": _row("Nueva nota", "New note", pt="Nova nota", fr="Nouvelle note", de="Neue Notiz", it="Nuova nota", pl="Nowa notatka", tr="Yeni not", ru="Новая заметка", ja="新しいメモ", ko="새 메모", zh="新建笔记"),
    "backup": _row("Respaldo", "Backup", pt="Backup", fr="Sauvegarde", de="Sicherung", it="Backup", pl="Kopia", tr="Yedek", ru="Резервная копия", ja="バックアップ", ko="백업", zh="备份"),
    "pc_mobile": _row("PC + celular", "PC + phone", pt="PC + celular", fr="PC + téléphone", de="PC + Handy", it="PC + telefono", pl="PC + telefon", tr="PC + telefon", ru="ПК + телефон", ja="PC + スマートフォン", ko="PC + 휴대폰", zh="电脑 + 手机"),
    "settings": _row("Configuración", "Settings", pt="Configurações", fr="Paramètres", de="Einstellungen", it="Impostazioni", pl="Ustawienia", tr="Ayarlar", ru="Настройки", ja="設定", ko="설정", zh="设置"),
    "lock": _row("Bloquear", "Lock", pt="Bloquear", fr="Verrouiller", de="Sperren", it="Blocca", pl="Zablokuj", tr="Kilitle", ru="Заблокировать", ja="ロック", ko="잠그기", zh="锁定"),
    "close": _row("Cerrar", "Close", pt="Fechar", fr="Fermer", de="Schließen", it="Chiudi", pl="Zamknij", tr="Kapat", ru="Закрыть", ja="閉じる", ko="닫기", zh="关闭"),
    "edit": _row("Editar", "Edit", pt="Editar", fr="Modifier", de="Bearbeiten", it="Modifica", pl="Edytuj", tr="Düzenle", ru="Изменить", ja="編集", ko="편집", zh="编辑"),
    "delete": _row("Eliminar", "Delete", pt="Excluir", fr="Supprimer", de="Löschen", it="Elimina", pl="Usuń", tr="Sil", ru="Удалить", ja="削除", ko="삭제", zh="删除"),
    "copy_password": _row("Copiar clave", "Copy password", pt="Copiar senha", fr="Copier le mot de passe", de="Passwort kopieren", it="Copia password", pl="Kopiuj hasło", tr="Parolayı kopyala", ru="Копировать пароль", ja="パスワードをコピー", ko="비밀번호 복사", zh="复制密码"),
    "copy_note": _row("Copiar nota", "Copy note", pt="Copiar nota", fr="Copier la note", de="Notiz kopieren", it="Copia nota", pl="Kopiuj notatkę", tr="Notu kopyala", ru="Копировать заметку", ja="メモをコピー", ko="메모 복사", zh="复制笔记"),
    "empty_vault": _row("El cofre está vacío", "The vault is empty", pt="O cofre está vazio", fr="Le coffre est vide", de="Der Tresor ist leer", it="La cassaforte è vuota", pl="Sejf jest pusty", tr="Kasa boş", ru="Сейф пуст", ja="保管庫は空です", ko="금고가 비어 있습니다", zh="保险库为空"),
    "no_matches": _row("Sin coincidencias", "No matches", pt="Sem resultados", fr="Aucun résultat", de="Keine Treffer", it="Nessun risultato", pl="Brak wyników", tr="Eşleşme yok", ru="Нет совпадений", ja="一致なし", ko="일치 항목 없음", zh="无匹配项"),
    "search": _row("Buscar por título, servicio, usuario o contenido", "Search title, service, username or content", pt="Buscar título, serviço, usuário ou conteúdo", fr="Rechercher titre, service, utilisateur ou contenu", de="Titel, Dienst, Benutzer oder Inhalt suchen", it="Cerca titolo, servizio, utente o contenuto", pl="Szukaj tytułu, usługi, użytkownika lub treści", tr="Başlık, hizmet, kullanıcı veya içerik ara", ru="Поиск по названию, сервису, пользователю или содержимому", ja="タイトル、サービス、ユーザー、内容を検索", ko="제목, 서비스, 사용자 또는 내용 검색", zh="搜索标题、服务、用户或内容"),
    "security": _row("Seguridad del cofre", "Vault security", pt="Segurança do cofre", fr="Sécurité du coffre", de="Tresorsicherheit", it="Sicurezza cassaforte", pl="Bezpieczeństwo sejfu", tr="Kasa güvenliği", ru="Безопасность сейфа", ja="保管庫のセキュリティ", ko="금고 보안", zh="保险库安全"),
    "encrypted_by_you": _row("Cifrado por tu contraseña", "Encrypted by your password", pt="Cifrado pela sua senha", fr="Chiffré par votre mot de passe", de="Mit Ihrem Passwort verschlüsselt", it="Cifrato dalla tua password", pl="Szyfrowane Twoim hasłem", tr="Parolanızla şifrelenir", ru="Зашифровано вашим паролем", ja="あなたのパスワードで暗号化", ko="사용자 비밀번호로 암호화", zh="由您的密码加密"),
    "intro_title": _row("LANKDEA // NÚCLEO CIFRADO", "LANKDEA // ENCRYPTED CORE", pt="LANKDEA // NÚCLEO CIFRADO", fr="LANKDEA // CŒUR CHIFFRÉ", de="LANKDEA // VERSCHLÜSSELTER KERN", it="LANKDEA // NUCLEO CIFRATO", pl="LANKDEA // SZYFROWANY RDZEŃ", tr="LANKDEA // ŞİFRELİ ÇEKİRDEK", ru="LANKDEA // ЗАШИФРОВАННОЕ ЯДРО", ja="LANKDEA // 暗号化コア", ko="LANKDEA // 암호화 코어", zh="LANKDEA // 加密核心"),
    "skip_intro": _row("Toca para continuar", "Tap to continue", pt="Toque para continuar", fr="Touchez pour continuer", de="Tippen zum Fortfahren", it="Tocca per continuare", pl="Dotknij, aby kontynuować", tr="Devam etmek için dokun", ru="Нажмите, чтобы продолжить", ja="タップして続行", ko="계속하려면 탭", zh="点击继续"),
}


def normalize_language(value: object) -> str:
    code = str(value or "es").lower()
    return code if code in _BY_CODE else "es"


def language_name(code: str) -> str:
    return _BY_CODE[normalize_language(code)].name


def translate(key: str, language: str = "es", *, default: str | None = None) -> str:
    row = TEXT.get(key)
    if row is None:
        return default if default is not None else key
    code = normalize_language(language)
    return row.get(code) or row.get("en") or row["es"]
