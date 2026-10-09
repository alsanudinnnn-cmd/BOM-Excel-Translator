# Excel Translator

A portable local web app that opens in the user's browser and translates `.xlsx` and legacy `.xls` workbooks through Azure Translator.

## Setup

1. Install Python 3.10+.
2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. Create `.env`, then add your Azure Translator key. Set `AZURE_TRANSLATOR_REGION` for a regional or multi-service Azure resource; leave it empty for a global Translator resource.
4. Start the app:

   ```powershell
   python app.py
   ```

## Build a portable Windows app

Run this in PowerShell from the project folder:

```powershell
.\build_portable.ps1
```

It creates `dist\ExcelTranslator.exe`. Copy the complete `dist` folder anywhere and keep its `.env` file beside the executable. Double-clicking `ExcelTranslator.exe` starts a private local server and opens the interface in the default browser. No Python installation is required on the target computer.

## Build the Windows installer

Install Inno Setup 6, then run:

```powershell
.\build_installer.ps1
```

The shareable installer is created at `installer\ExcelTranslatorSetup.exe`. It installs for the current Windows user, creates Start Menu and optional desktop shortcuts, and includes an uninstaller. The bundled `.env` gives recipients access to the configured Azure subscription, so only share the installer with trusted people.

## What is preserved

- `.xlsx`: sheets, formulas, values, cell styles, merged cells, and common workbook formatting are preserved. Only non-formula text cells are translated.
- `.xls`: the workbook is read and exported as `.xlsx`. Its cell text and sheet layout are retained, but legacy `.xls` formatting and formulas cannot be guaranteed in this conversion path.

The app sends only text-cell values to Azure Translator. Credentials stay in your local `.env` file.

## Monthly character indicator

The app keeps a local estimate of successful Azure Translator characters in `usage.json` beside the executable. It shows the used amount, remaining amount from the 2,000,000-character allowance, the next local calendar-month reset, and an estimate for the selected workbook. This is not an account-wide Azure meter: usage from another app, computer, or copy of this portable folder is not included.

Azure Translator uses its v3 Text Translation endpoint with the subscription-key header and, when configured, the resource-region header. See the [official Azure Translator REST API reference](https://learn.microsoft.com/en-us/azure/ai-services/translator/text-translation/reference/v3/reference).
