# ecoNET-300 Home Assistant Integration

[![Code Formatter](https://img.shields.io/badge/Code%20Formatter-Ruff-000000?style=for-the-badge&logo=python)](https://github.com/astral-sh/ruff)
[![Latest Release](https://img.shields.io/github/v/release/jontofront/ecoNET-300-Home-Assistant-Integration?style=for-the-badge)](https://github.com/jontofront/ecoNET-300-Home-Assistant-Integration/releases)
[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5?style=for-the-badge&logo=homeassistant)](https://github.com/hacs/integration)
[![Active Installs](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.econet300.total&label=Active%20Installs&style=for-the-badge&logo=homeassistant&color=41BDF5)](https://analytics.home-assistant.io)
[![HACS Action](https://img.shields.io/badge/HACS%20Action-passing-brightgreen?style=for-the-badge&logo=github)](https://github.com/jontofront/ecoNET-300-Home-Assistant-Integration/actions/workflows/hacs.yml)
[![Stability](https://img.shields.io/badge/Stability-Stable-2ecc71?style=for-the-badge)](https://guidelines.denpa.pro/stability#stable)
[![Hassfest](https://img.shields.io/badge/Hassfest-Validated-brightgreen?style=for-the-badge&logo=homeassistant)](https://github.com/jontofront/ecoNET-300-Home-Assistant-Integration/actions/workflows/hassfest.yaml)

**Note:** This repository is a fork of the original [pblxptr/ecoNET-300-Home-Assistant-Integration](https://github.com/pblxptr/ecoNET-300-Home-Assistant-Integration). Most of the work was done by [@pblxpt](https://github.com/pblxpt), and we are very grateful for their efforts. Additionally, I maintained and supported this code up to version v0.3.3.

<div align="center">

| Home Assistant                                                                                                                                 | ecoNET300                                                                                                                                         | device                                                                                                                                                       |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| <img src="https://raw.githubusercontent.com/jontofront/ecoNET-300-Home-Assistant-Integration/master/images/ha.png" width="100" height="100" /> | <img src="https://raw.githubusercontent.com/jontofront/ecoNET-300-Home-Assistant-Integration/master/images/econet.webp" width="95" height="95" /> | <img src="https://raw.githubusercontent.com/jontofront/ecoNET-300-Home-Assistant-Integration/master/images/econet300_device.jpg" width="100" height="100" /> |

</div>

## Overview

The **ecoNET300 Home Assistant Integration** allows local control and monitoring of ecoNET300 devices directly from Home Assistant. It communicates over your local network via the ecoNET-300's native REST API, avoiding any external cloud services.

### ✨ Features

- **Local Operation**: No dependency on econet24.com cloud services
- **Easy Configuration**: Integrate directly via Home Assistant UI
- **Boiler Control**: Turn your boiler ON/OFF directly from Home Assistant
- **Real-time Monitoring**: Monitor temperatures, fuel levels, and system status
- **Comprehensive API Access**: Access to 48 different API endpoints
- **Multiple Entity Types**: Sensors, Binary Sensors, Switches, and Number entities
- **Diagnostics Support**: Download comprehensive diagnostics for troubleshooting

### 🌐 Language Support

The integration supports **6 languages** with comprehensive translations:

| Language     | Code | Status      | Coverage         |
| ------------ | ---- | ----------- | ---------------- |
| 🇬🇧 English   | `en` | ✅ Complete | Base language    |
| 🇵🇱 Polish    | `pl` | ✅ Complete | Full translation |
| 🇨🇿 Czech     | `cs` | ✅ Complete | 348 parameters   |
| 🇫🇷 French    | `fr` | ✅ Complete | 876 parameters   |
| 🇺🇦 Ukrainian | `uk` | ✅ Complete | 855 parameters   |

### 🏠 Supported Devices

- **ecoMAX810P-L TOUCH** controller from [Plum Sp. z o.o.](https://www.plum.pl/)
- **ecoMAX850R2-X** pellet boiler controller
- **ecoMAX360** boiler controller
- **ecoMAX860P2-N** boiler controller
- **ecoMAX860P3-V** boiler controller
- **ecoSOL500** solar collector system controller
- **ecosol301**
- **ecoSOL** solar thermal controller
- **SControl MK1** control module
- Other ecoNET300 compatible devices

---

## 📋 Table of Contents

1. [Installation](#installation)
2. [Upgrading](#upgrading)
3. [Configuration](#configuration)
4. [Entities](#entities)
5. [Contributing](#contributing)
6. [Acknowledgments](#acknowledgments)

---

## 🚀 Installation

### HACS (Recommended)

1. Install and configure [HACS](https://hacs.xyz/).
2. Add this repository as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/) using:

```text
https://github.com/jontofront/ecoNET-300-Home-Assistant-Integration
```

3. In HACS, search for **"ecoNET300"**, install the integration.
4. Restart Home Assistant.

### Manual Installation

1. Download or clone this repository.
2. Copy `custom_components/econet300` into your `<config_directory>/custom_components/`.

```text
<config directory>/
|-- custom_components/
|   |-- econet300/
|       |-- [...]
```

3. Restart Home Assistant.

---

## 🔄 Upgrading

### From v1.1.x to v1.2.x

**v1.2.0 introduces significant new features** including 165+ dynamic entities, parameter locking, and repair issues system.

**Good news:** No manual migration required! Your existing configuration will continue to work.

**After upgrading:**
1. Restart Home Assistant
2. Check **Settings → Devices → ecoNET300** for new entities
3. New CONFIG category entities are disabled by default - enable as needed

| What Changes | Details |
|-------------|---------|
| Existing entities | Continue working unchanged |
| Entity IDs | Stable, no changes |
| New entities | Auto-discovered, CONFIG disabled by default |
| Configuration | Preserved, no reconfiguration needed |

**📖 [Complete Migration Guide](docs/MIGRATION.md)**

---

## ⚙️ Configuration

Integrate ecoNET300 via the user interface:

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=econet300)

<details>
<summary><b>Manual Configuration Steps</b></summary>

Apart from using 'My button' (in case it doesn't work) you can also perform the following steps manually:

1. Go to **Settings > Devices & Services** in Home Assistant.
2. Click **Add Integration**.
3. Search and select **"ecoNET300"**.
4. In the bottom right, click on the Add Integration button.
5. From the list, search and select **"ecoNET300"**.

![Search dialog](https://raw.githubusercontent.com/jontofront/ecoNET-300-Home-Assistant-Integration/master/images/search.png)

6. Enter your local device IP/domain and local credentials (not econet24.com credentials). **"Submit"**.

**Host**: Local IP/domain of your device.

**Username**: Local username (NOT the username that you use to login to econet24.com!).

**Password**: Local password (NOT the password that you use to login to econet24.com!).

![Configuration dialog](https://raw.githubusercontent.com/jontofront/ecoNET-300-Home-Assistant-Integration/master/images/configure.png)

7. Your device should now be available in your Home Assistant installation.

![Success](https://raw.githubusercontent.com/jontofront/ecoNET-300-Home-Assistant-Integration/master/images/success.png)

</details>

---

## 🏠 Entities

The integration provides multiple entity types:

| Type | Count | Description |
|------|-------|-------------|
| Sensors | 50+ | Temperature, status, system info |
| Binary Sensors | 25+ | Pumps, fans, connections |
| Switches | 1 | Boiler ON/OFF control |
| Select | 1 | Heater mode (Winter/Summer/Auto) |
| Number | 15+ | Temperature setpoints |

**Key Features:**

- **Boiler Control**: Turn boiler ON/OFF directly from Home Assistant
- **Temperature Setpoints**: Control heating and hot water temperatures
- **Heater Mode**: Switch between Winter, Summer, and Auto modes
- **Real-time Monitoring**: All sensors update in real-time from your device

**📖 [Complete Entity Reference](docs/ENTITIES.md)** - Full list of all entities with descriptions

---

## 🔧 Diagnostics

The integration includes comprehensive diagnostics support to help troubleshoot issues. Download detailed system information including entity states, API data, and configuration details.

**📖 [Complete Diagnostics Documentation](docs/DIAGNOSTICS.md)**

### Quick Start

1. Go to **Settings > Devices & Services** in Home Assistant
2. Find your **ecoNET300** integration
3. Click the **Download diagnostics** button
4. Share the redacted diagnostics file for support

**Features:**

- ✅ Automatic sensitive data redaction
- ✅ Complete API endpoint data
- ✅ Entity states and attributes
- ✅ System configuration details

---

## 📁 Project Structure

```text
ecoNET-300-Home-Assistant-Integration/
├── custom_components/econet300/     # Home Assistant integration
├── docs/                            # Complete documentation
├── scripts/                         # Development and utility scripts
├── tests/                           # Integration tests
└── [standard project files]
```

### 🔧 **Essential Scripts** (in `scripts/`)

- **test_api_endpoints.py** - Test all API endpoints and validate responses
- **check_translations.py** - Validate translation files for consistency
- **language_finder.py** - Find and analyze language-specific content
- **README.md** - Scripts documentation and usage instructions

### 📚 **Essential Documentation** (in `docs/`)

- **[ENTITIES.md](docs/ENTITIES.md)** - Complete entity reference (sensors, switches, numbers)
- **[MIGRATION.md](docs/MIGRATION.md)** - Migration guide for upgrading between versions
- **[DIAGNOSTICS.md](docs/DIAGNOSTICS.md)** - Diagnostics documentation and troubleshooting
- **[API_V1_DOCUMENTATION.md](docs/API_V1_DOCUMENTATION.md)** - Complete API documentation
- **[devices/](docs/devices/)** - Device-specific documentation (ecoMAX, ecoSOL)

---

## 📋 Versions

For detailed version information and changelog, see [CHANGELOG.md](CHANGELOG.md).

### Latest Features

- **Complete Boiler Status Codes**: All 27 operation status codes supported (including prevention, calibration, maintenance, etc.)
- **Repair Issues System**: Automatic detection of connection failures with easy one-click fix in Settings → System → Repairs
- **Reconfiguration Flow**: Update connection settings (host, username, password) after initial setup via integration options
- **Diagnostics Support**: Comprehensive diagnostics for troubleshooting issues
- **Boiler Control**: Turn boiler ON/OFF directly from Home Assistant
- **Temperature Setpoints**: Full control over heating and hot water temperatures
- **Mixer Support**: Smart entity creation for up to 6 mixer temperature setpoints
- **ecoSTER Integration**: Support for 8 room thermostats
- **ecoSOL 500 Support**: Solar collector system integration
- **Multi-language**: 6 language support (English, Polish, Czech, French, Ukrainian)

---

## 🤝 Contributing

We welcome contributions! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### Testing

Use the provided scripts in the `scripts/` directory to test API endpoints and validate translations.

---

## 🙏 Acknowledgments

- **[@jontofront](https://github.com/jontofront)** - Current maintainer and developer
- **[@pblxpt](https://github.com/pblxpt)** - Original developer and maintainer up to v0.3.3
- **[@KirilKurkianec](https://github.com/KirilKurkianec)** - Contributor and supporter
- **ecoNET300 Community** - For testing, feedback, and support
- **Plum Sp. z o.o.** - For creating the ecoNET300 system

---

## ⚠️ Disclaimer

This integration is not officially affiliated with or endorsed by Plum Sp. z o.o. Use at your own risk. The developers are not responsible for any damage to your equipment or system.

---

## 📞 Support

If you encounter any issues or have questions:

1. Check the [API Documentation](docs/API_V1_DOCUMENTATION.md)
2. Search existing [Issues](https://github.com/jontofront/ecoNET-300-Home-Assistant-Integration/issues)
3. Create a new issue with detailed information about your problem

---

_This README was last updated on 2025-01-28 with v1.2.0 release._
