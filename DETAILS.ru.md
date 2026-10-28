# Подробности и предыдущая документация

Актуальная стартовая страница: [README.md](README.md). Ниже сохранены технические подробности и исторический протокол; при расхождении по текущему выпуску ориентируйтесь на README и Releases.

# Acronis Image Tool

Утилита Windows для поиска, каталогизации и копирования образов `.tib` / `.tibx`.
Поддерживает SMB, FTP и публичные Web / HTTPS каталоги POScenter, фильтры по
устройству, процессору и ОС, локальные метаданные, проверку наличия файлов
на выбранном носителе и копирование с прогрессом.

## Скачать

В [Releases](https://github.com/jeronimo701/AcronisImageTool/releases) скачайте
`AcronisImageTool-Setup-snapshot-2026-10-28.exe`. Распакуйте установщиком
в доступную для записи папку и запустите `AcronisImageTool.exe`. Python не нужен.
Это снимок проекта от 28 октября 2026 года; авторская версия в исходниках не указана.

По умолчанию выбран публичный каталог https://fs.poscenter.org. Для SMB / FTP
укажите свой сервер, папку и учётные данные. Сохранённые реквизиты хранятся локально
в `app_settings.json` открытым текстом; не передавайте этот файл другим людям.
Сохранённые списки находятся в `catalogs/`, изменения описаний — в `metadata_overrides.json`.
Публичная поставка не содержит рабочих настроек, паролей, каталогов или самих образов ОС.
Рабочие каталоги и метаданные создаются при использовании приложения.

## Запуск из исходников

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

## Проверка и сборка

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File .\build_portable.ps1
```

Результат — `dist/AcronisImageTool/`. Копируйте папку целиком.
Код автора распространяется по LICENSE.txt и LICENSE-SCOPE.md.
Сторонние компоненты сохраняют свои лицензии, см. THIRD-PARTY.md.
Программа не включает ПО Acronis и не восстанавливает образы на физические диски.
