# CurseForge Modpack Downloader

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)
![CurseForge](https://img.shields.io/badge/CurseForge-API-orange)

Automatically downloads mods, resource packs, and shader packs from CurseForge modpacks, sorts files into subfolders, downloads required dependencies, skips already downloaded files, and verifies what is missing.

Автоматически скачивает моды, ресурспаки и шейдерпаки из модпаков CurseForge, раскладывает файлы по подпапкам, скачивает обязательные зависимости, пропускает уже скачанные файлы и проверяет, чего не хватает.

---

## Contents

- [English](#english)
  - [Features](#features)
  - [Requirements](#requirements)
  - [Installation](#installation)
  - [Quick Start](#quick-start)
  - [Usage](#usage)
  - [Commands](#commands)
  - [Output Structure](#output-structure)
  - [Notes](#notes)
- [Русский](#русский)
  - [Возможности](#возможности)
  - [Требования](#требования)
  - [Установка](#установка)
  - [Быстрый старт](#быстрый-старт)
  - [Использование](#использование)
  - [Команды](#команды)
  - [Структура выходной папки](#структура-выходной-папки)
  - [Заметки](#заметки)
- [License](#license)

---

# English

## Features

- Download from ZIP modpack archives
- Download from `manifest.json`
- Download from `modlist.html`
- Automatic file type detection
- Automatic sorting into subfolders:
  - `mods`
  - `resourcepacks`
  - `shaderpacks`
  - `datapacks`
  - `worlds`
- Automatic download of required mod dependencies
- Recursive dependency resolution
- Skip already downloaded files
- Save download cache
- Save download report
- Verify missing files
- Show modpack info:
  - modpack name
  - version
  - author
  - Minecraft version
  - loader type
  - total file count
- Supports:
  - Forge
  - Fabric
  - NeoForge
  - Quilt
- Interactive menu
- Windows launcher via `start.bat`

## Requirements

- Python 3.10 or newer
- `requests`
- `beautifulsoup4`
- CurseForge API key

Get a free API key here:

https://console.curseforge.com/

## Installation

Clone the repository:

```bash
git clone https://github.com/Wrx1z/curseforge-modpack-downloader.git
cd curseforge-modpack-downloader
```

Install dependencies:

```bash
pip install -r requirements.txt
```

or:

```bash
pip install requests beautifulsoup4
```

## Quick Start

### Windows

1. Install Python
2. Run `start.bat`
3. On first launch, enter your CurseForge API key
4. Choose a mode and follow the prompts

`start.bat` can:
- check Python
- install required libraries
- ask for API key
- save API key into `api_key.txt`
- launch the main script

## Usage

### Interactive mode

```bash
python curseforge_downloader.py
```

### Command line

Download from ZIP archive:

```bash
python curseforge_downloader.py zip "modpack.zip" -o "output_folder"
```

Download from `manifest.json`:

```bash
python curseforge_downloader.py manifest "manifest.json" -o "output_folder"
```

Download from `modlist.html`:

```bash
python curseforge_downloader.py modlist "modlist.html" -o "output_folder"
```

Verify downloaded files:

```bash
python curseforge_downloader.py verify -o "output_folder"
```

Show modpack info:

```bash
python curseforge_downloader.py info "modpack.zip"
python curseforge_downloader.py info "manifest.json"
```

Pass API key manually if needed:

```bash
python curseforge_downloader.py zip "modpack.zip" -o "output_folder" --api-key "YOUR_KEY"
```

## Commands

| Command | Description |
|--------|-------------|
| `zip` | Extract ZIP and download files |
| `manifest` | Download from manifest.json |
| `modlist` | Download from modlist.html |
| `verify` | Verify downloaded files |
| `info` | Show modpack information |

## Output Structure

Typical output folder:

```text
output_folder/
├── mods/
├── resourcepacks/
├── shaderpacks/
├── datapacks/
├── worlds/
├── config/
├── _download_cache.json
└── _download_report.json
```

## API Key

The program loads the API key in this order:

1. From `--api-key`
2. From `api_key.txt`

If `api_key.txt` does not exist, `start.bat` can ask for the key and create the file automatically.

## Dependency Resolution

When downloading mods, the program checks required dependencies and downloads them automatically. Dependencies of dependencies are also resolved recursively.

Only required dependencies are downloaded automatically.

## Overrides

If the modpack ZIP contains an `overrides` folder, its contents are copied into the output folder automatically. This includes configs, bundled mods, resource packs, shader packs, and other files included by the modpack author.

## Notes

- A CurseForge API key is required for downloading
- ZIP and `manifest.json` are the most reliable sources
- `modlist.html` is supported but less reliable
- Some files may fail if they are private, removed, or restricted
- Already downloaded files are skipped automatically
- Files are not overwritten if they already exist
- Paths with spaces and special characters are supported

---

# Русский

## Возможности

- Скачивание из ZIP-архивов модпаков
- Скачивание из `manifest.json`
- Скачивание из `modlist.html`
- Автоматическое определение типа файлов
- Автоматическая сортировка по подпапкам:
  - `mods`
  - `resourcepacks`
  - `shaderpacks`
  - `datapacks`
  - `worlds`
- Автоматическое скачивание обязательных зависимостей модов
- Рекурсивное разрешение зависимостей
- Пропуск уже скачанных файлов
- Сохранение кэша скачивания
- Сохранение отчёта о скачивании
- Проверка недостающих файлов
- Показ информации о модпаке:
  - название
  - версия
  - автор
  - версия Minecraft
  - тип загрузчика
  - общее количество файлов
- Поддержка:
  - Forge
  - Fabric
  - NeoForge
  - Quilt
- Интерактивное меню
- Запуск через `start.bat` на Windows

## Требования

- Python 3.10 или новее
- `requests`
- `beautifulsoup4`
- API ключ CurseForge

Бесплатно получить API ключ можно здесь:

https://console.curseforge.com/

## Установка

Клонируй репозиторий:

```bash
git clone https://github.com/Wrx1z/curseforge-modpack-downloader.git
cd curseforge-modpack-downloader
```

Установи зависимости:

```bash
pip install -r requirements.txt
```

или:

```bash
pip install requests beautifulsoup4
```

## Быстрый старт

### Windows

1. Установи Python
2. Запусти `start.bat`
3. При первом запуске введи API ключ CurseForge
4. Выбери режим и следуй подсказкам

`start.bat` умеет:
- проверять Python
- устанавливать нужные библиотеки
- запрашивать API ключ
- сохранять API ключ в `api_key.txt`
- запускать основной скрипт

## Использование

### Интерактивный режим

```bash
python curseforge_downloader.py
```

### Командная строка

Скачать из ZIP-архива:

```bash
python curseforge_downloader.py zip "modpack.zip" -o "output_folder"
```

Скачать из `manifest.json`:

```bash
python curseforge_downloader.py manifest "manifest.json" -o "output_folder"
```

Скачать из `modlist.html`:

```bash
python curseforge_downloader.py modlist "modlist.html" -o "output_folder"
```

Проверить скачанные файлы:

```bash
python curseforge_downloader.py verify -o "output_folder"
```

Показать информацию о модпаке:

```bash
python curseforge_downloader.py info "modpack.zip"
python curseforge_downloader.py info "manifest.json"
```

Если нужно, ключ можно передать вручную:

```bash
python curseforge_downloader.py zip "modpack.zip" -o "output_folder" --api-key "ВАШ_КЛЮЧ"
```

## Команды

| Команда | Описание |
|--------|----------|
| `zip` | Извлечь ZIP и скачать файлы |
| `manifest` | Скачать из manifest.json |
| `modlist` | Скачать из modlist.html |
| `verify` | Проверить скачанные файлы |
| `info` | Показать информацию о модпаке |

## Структура выходной папки

Типичная выходная папка:

```text
output_folder/
├── mods/
├── resourcepacks/
├── shaderpacks/
├── datapacks/
├── worlds/
├── config/
├── _download_cache.json
└── _download_report.json
```

## API ключ

Программа загружает API ключ в таком порядке:

1. Из `--api-key`
2. Из `api_key.txt`

Если `api_key.txt` отсутствует, `start.bat` может сам запросить ключ и автоматически создать этот файл.

## Зависимости

При скачивании модов программа проверяет обязательные зависимости и скачивает их автоматически. Зависимости зависимостей тоже разрешаются рекурсивно.

Автоматически скачиваются только обязательные зависимости.

## Overrides

Если ZIP-архив модпака содержит папку `overrides`, её содержимое автоматически копируется в выходную папку. Это включает конфиги, встроенные моды, ресурспаки, шейдерпаки и другие файлы, вложенные автором сборки.

## Заметки

- Для скачивания нужен API ключ CurseForge
- ZIP и `manifest.json` — самые надёжные источники
- `modlist.html` тоже поддерживается, но менее надёжен
- Некоторые файлы могут не скачаться, если они приватные, удалённые или ограниченные
- Уже скачанные файлы автоматически пропускаются
- Файлы не перезаписываются, если уже существуют
- Поддерживаются пути с пробелами и специальными символами

---

## License

MIT License
