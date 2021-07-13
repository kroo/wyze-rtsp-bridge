# Wyze RTSP Bridge

<div align="center">

[![Build status](https://github.com/kroo/wyze-rtsp-bridge/workflows/build/badge.svg?branch=master&event=push)](https://github.com/kroo/wyze-rtsp-bridge/actions?query=workflow%3Abuild)
[![Python Version](https://img.shields.io/pypi/pyversions/wyze-rtsp-bridge.svg)](https://pypi.org/project/wyze-rtsp-bridge/)
[![Dependencies Status](https://img.shields.io/badge/dependencies-up%20to%20date-brightgreen.svg)](https://github.com/kroo/wyze-rtsp-bridge/pulls?utf8=%E2%9C%93&q=is%3Apr%20author%3Aapp%2Fdependabot)

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Security: bandit](https://img.shields.io/badge/security-bandit-green.svg)](https://github.com/PyCQA/bandit)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/kroo/wyze-rtsp-bridge/blob/master/.pre-commit-config.yaml)
[![Semantic Versions](https://img.shields.io/badge/%F0%9F%9A%80-semantic%20versions-informational.svg)](https://github.com/kroo/wyze-rtsp-bridge/releases)
[![License](https://img.shields.io/github/license/kroo/wyze-rtsp-bridge)](https://github.com/kroo/wyze-rtsp-bridge/blob/master/LICENSE)

A server that transcodes wyze native video streams to rtsp.

</div>


<div style="font-weight: bold; font-size: 24px">
This repository is still a work in progress.
</div>

This project is based on [kroo/wyzecam](https://github.com/kroo/wyzecam)
and [gst-rtsp-server](https://github.com/GStreamer/gst-rtsp-server), look there for more details on how this works.

## Getting Started

### From Source

If you want to use wyze-rtsp-bridge without Docker, you will need to install gstreamer and gst-rtsp-server libraries:

```bash
sudo apt-get install -y \
    libcairo-dev \
    build-essential \
    libgirepository1.0-dev \
    libgstrtspserver-1.0-dev \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-doc \
    gstreamer1.0-tools
```

Install a copy of the `libIOTCAPIs_ALL` shared library (as per https://github.com/kroo/wyzecam#installation):

```bash
$ unzip TUTK_IOTC_Platform_14W42P1.zip
$ cd Lib/Linux/x64/
$ g++ -fpic -shared -Wl,--whole-archive libAVAPIs.a libIOTCAPIs.a -Wl,--no-whole-archive -o libIOTCAPIs_ALL.so
$ cp libIOTCAPIs_ALL.so /usr/local/lib/
```

Then you can install wyze-rtsp-server:

```bash
$ git clone https://github.com/kroo/wyze-rtsp-bridge.git
$ cd wyze-rtsp-bridge/
$ poetry install
```

You should then have wyze-rtsp-bridge installed in your path:

```bash
$ poetry run wyze-rtsp-bridge --help

Usage: wyze-rtsp-bridge [OPTIONS]

  Starts a server that translates local wyze camera video streams to rtsp.

Options:
  -v, --version       Prints the version of the wyze-rtsp-bridge package.
  -c, --cameras TEXT  A list of camera MAC addresses to expose.  Use this
                      option to filter the cameras exposed by the bridge (a
                      good idea for low-resource systems like Raspberry Pis,
                      if you have a lot of cameras).

  -p, --port INTEGER  [default: 8554]
  -c, --config TEXT   The path to the configuration file for wyze-rtsp-bridge
                      [default: ~/.config/wyze_rtsp_bridge/config.yml]

  --create-config     Creates a config file at ~/.wyzecam/config.yml
                      [default: False]

  --help              Show this message and exit.
```

### Docker (TBD)

You can run wyze-rtsp-bridge via docker, though you will need to provide the path to the tutk library, along with your
credentials:

```bash
docker run -e WYZE_EMAIL=... -e WYZE_PASSWORD=... --mount type=bind,source=/path/to/tutk/libIOTCAPIs_ALL.so,target=/usr/local/lib/libIOTCAPIs_ALL.so --network host -it kroo/wyze-rtsp-bridge:latest
```

Unfortunately this seems to not pick up the wyze cameras on the local network, likely due to docker networking.  More to come....

## 📈 Releases

You can see the list of available releases on the [GitHub Releases](https://github.com/kroo/wyze-rtsp-bridge/releases)
page.

We follow [Semantic Versions](https://semver.org/) specification.

We use [`Release Drafter`](https://github.com/marketplace/actions/release-drafter). As pull requests are merged, a draft
release is kept up-to-date listing the changes, ready to publish when you’re ready. With the categories option, you can
categorize pull requests in release notes using labels.

For Pull Request this labels are configured, by default:

|               **Label**               |  **Title in Releases**  |
| :-----------------------------------: | :---------------------: |
|       `enhancement`, `feature`        |       🚀 Features       |
| `bug`, `refactoring`, `bugfix`, `fix` | 🔧 Fixes & Refactoring  |
|       `build`, `ci`, `testing`        | 📦 Build System & CI/CD |
|              `breaking`               |   💥 Breaking Changes   |
|            `documentation`            |    📝 Documentation     |
|            `dependencies`             | ⬆️ Dependencies updates |

You can update it
in [`release-drafter.yml`](https://github.com/kroo/wyze-rtsp-bridge/blob/master/.github/release-drafter.yml).

GitHub creates the `bug`, `enhancement`, and `documentation` labels for you. Dependabot creates the `dependencies`
label. Create the remaining labels on the Issues tab of your GitHub repository, when you need them.

## 🛡 License

[![License](https://img.shields.io/github/license/kroo/wyze-rtsp-bridge)](https://github.com/kroo/wyze-rtsp-bridge/blob/master/LICENSE)

This project is licensed under the terms of the `MIT` license.
See [LICENSE](https://github.com/kroo/wyze-rtsp-bridge/blob/master/LICENSE) for more details.

## 📃 Citation

```
@misc{wyze-rtsp-bridge,
  author = {kroo},
  title = {A server that transcodes wyze native video streams to rtsp},
  year = {2021},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/kroo/wyze-rtsp-bridge}}
}
```
