<p align="center"><img src="https://i.imgur.com/KrBqDy3.png" alt="Signal" width="500" height="500"></p>

<h1 align="center">Signal user reference guide</h1>
<p align="center">This guide describes the Signal basic concept, usage, settings, and library re-usage <br><br>
The document is currently under construction</p> 


<details><summary><h1>Contents</h1></summary>
       
* [Signal](#signal)
  * [Signal general overview](#signal-general-overview)
  * [Important notes](#important-notes)
  * [Release info](#release-info)
   

* [Graphic User Interface](#graphic-user-interface)
  * [GUI overview](#gui-overview)
  * [Main Window](#main-window)
    * [Overview](#main-window-overview)
    * [Features]
      * [Transactions sending]
      * [Data exchange]
      * [Validations]
      * [Search line](#search-line)
      * [Hide secrets](#hide-secrets)
      * [Windows hotkeys](#windows-hotkeys)
       
    * Tools
      * [Connector] 
      * [Echo-test]
      * [Keep alive]
      * [Transactions auto-repeat](#transactions-auto-repeat)
      * [Reversal](#reversal)
      * [Complex fields parser](#complex-fields-parser)
      * [Print data](#print-data)
      * [Fields generators](#fields-generators)
      * [Secret features](#secret-features)
  
  * [Settings Window](#settings-window)
    * [Settings Window overview](#settings-window-overview)
    * [Triggers](#triggers)
    * [Validations](#validations)      

  * [Specification Window](#specification-window)
    * [Specification Window overview](#specification-window-overview)
    * [Field parameters](#field-parameters)
    * [Extended field parameters](#extended-field-parameters)
    * [MTI settings](#mti-settings)
    * [Set specification](#set-specification)
    * [Save specification](#save-specification)


* [HTTP Transaction API](#http-transaction-api)
  * [Short API reference](#short-api-reference)
  * [Complete API reference](#complete-api-reference)
  * [Data models]
  * [Postman collection](#postman-collection)
  
  
* [Command Line Interface](#command-line-interface)
  * [CLI usage](#cli-usage)
  * [CLI examples](#cli-examples)
  * [CLI output](#cli-output)
 
 
* [Library re-usage](#library-re-usage)
  * [Requirements](#requirements)
  * [Library installation](#library-installation)
  * [Modules purpose](#modules-purpose)
  * [Logging](#logging)
  * [Modules usage example](#modules-usage-example)
    * [Preparation](#preparation)
    * [Code examples](#code-examples)
  * [Compilation of executable binary](#compilation-of-executable-binary)
  * [Recommendations](#recommendations)
  * [Data models](#data-models)
    * [Transaction](#transaction)
    * [Config](#config)
    * [Specification](specification)
  * [Specification settings](#specification-settings)
    * [Specification Overview](#specification-overview) 
    * [Settings description](#settings-description)
    * [Specification backup](#specification-backup)
    * [Remote specification](#remote-specification)
    * [Remote specification endpoint setting](#remote-specification-endpoint-setting)
    * [Remote spec endpoint code example](#remote-spec-endpoint-code-example)
   

* [Fields validation](#fields-validation)
  * [Main validation](#main-validation)
  * [Extended validation](#extended-validation)
  * [Violation mode](#violation-mode)
  * [Directions](#directions)
  * [Complex fields representation](#complex-fields-representation)
  * [Manual entry mode](#manual-entry-mode)


* [Configuration](#configuration)
  * [Config overview](#config-overview)
  * [Config file](#config-file)
  * [Settings](#settings)
    * [Remote host](#remote-host)
    * [Specification](#specification)
    * [On startup](#on-startup)
    * [Log](#log)
    * [Validation](#validation)
    * [Fields](#fields)
   
 
 * [Transaction data files](#transaction-data-files)
   * [Data files overview](#data-files-overview)
   * [The data formats description](#the-data-formats-description)
   * [Loading to the SIGNAL](#loading-to-the-signal)
   * [Save transaction to file](#save-transaction-to-file)


* [Data storage](#data-storage)
  * [Default messages](#default-messages)
  * [Dictionaries](#dictionaries)
  * [License info](#license-info)
  * [Settings storage](#settings-storage)
  * [Specification backup](#specification-backup)


* [Logging](#logging)
  * [Log levels](#log-levels)
  * [Storage and rotation](#storage-and-rotation)
  * [Hide secrets](#hide-secrets)


* [Bugs](#bugs)
  * [List of known bugs](#list-of-known-bugs)


* [About SIGNAL](#about-signal)
  * [Concept](#concept) 
  * [License](#license)
  * [Resources](#resources)
  * [Support](#support)
  * [Author](#author)

</details>

# Signal

## Signal general overview

The Signal simplifies the sending of banking card e-commerce transactions to banking card processing systems using a 
useful visual and program interface. It uses ISO-8583 E-pay protocol for transactions sending, instead of PSP. It can be
used during the Payment Systems certification test, for checking and setting up the system on the test environment, 
during the application development process, and so on.

The Signal has three interfaces, which lead to the single core - Graphic User Interface, WEB Application Program 
Interface, and Command line interface. Generally speaking, they do the same things but use different points of 
interaction with their own specific features

Also, the Signal builds like a kit of weakly connected modules like a Parser, Connector, Queue, etc. It allows to 
reuse or extend the Signal's functionality making emulators, loaders, parsers, converters, application interfaces, 
and many other things based on [Signal modules](#library-re-usage) 

In case of any questions about SIGNAL [contact the author](#author). Your feedback and suggestions are general drivers 
of the Signal evolution

## Important notes

* Allowed usage on test environment only. SIGNAL only implements basic security checks
* At the moment SIGNAL doesn't support byte-fields
* GUI tests were made on Windows 10/11 x64 only
* The application and the document are currently under construction


## Release info

What's new is the Signal v0.19

* New features
  * Web API in GUI and CLI mode
  * The Postman collection
  * Toolbar on main window
  * Standalone user reference guide, available in browser

* Updates
  * The main window buttons set is revised. All the tools moved to the toolbar
  * Renovation of the settings window 
  * The "settings" and the "about" windows are merged
  * Updated user reference guide 
  
  
* Fixed
  * Force fields validation does not work in some cases 
  * Code optimization
  

# Graphic User Interface

## GUI overview

⚠️Only Windows x64 build exists. Use the source code to run SIGNAL on another platform. Tests were done on 
Windows 10-11 only

SIGNAL GUI is a friendly interface, based on the SIGNAL library. Since v0.15 SIGNAL GUI is released as a 
binary `.exe` file. No dependencies need to run the SIGNAL, it is ready to use from the box. No installation or 
settings are needed to run SIGNAL GUI on a Windows machine. Run the `signal.exe` executable file to start the SIGNAL

Check the parameters, opened by the "Configuration" button to make your settings  

![image](https://i.imgur.com/guPzcTT.png)

## Main Window

The MainWidow is a generic user interaction point. The main purpose is transaction data representation, data 
validations, and generators, access to the transaction processing tools, sending and receiving transactions

### Main Window tools

The MainWidow is an access point to the transactions management tools. Not all the tools are presented in the MainWindow 
directly. This chapter describes the MainWindow tools' purpose and best usage practices

#### Search line

Accessible by `Ctrl + F` key sequence. The search line ...

#### Complex fields parser

#### Reversal

#### Transactions auto-repeat

#### Print data

#### Fields generators

#### Secret features



## Specification Window

### Specification Window overview

### Field parameters

### Extended field parameters

### MTI settings

### Set specification

### Save specification

## Settings Window

### Settings Window overview

### Triggers

### Validations

## Windows hotkeys

The list of key sequences and corresponding actions 

| Key sequence                      | MainWindow                     | SpecWindow                       |
|-----------------------------------|--------------------------------|----------------------------------|
| F1                                | About SIGNAL                   | -                                |
| Ctrl + Enter                      | Send transaction               | -                                |
| Ctrl + Shift + Enter              | Reverse last transaction       | -                                |
| Ctrl + Alt + Enter                | Send Echo-Test                 | -                                |
| Ctrl + N                          | Add new field                  | Add new field                    |
| Ctrl + Shift + N                  | Add new subfield               | Add new subfield                 |
| Ctrl + Shift + V                  | Validate current message       | -                                |
| Ctrl + F                          | Search                         | Search                           |
| Delete                            | Remove field                   | Remove field                     |
| Ctrl + E                          | Edit current field data        | Edit current field description   |
| Ctrl + W                          | Edit current field number      | Edit current field number        |
| Ctrl + R                          | Reconnect to host              | -                                |
| Ctrl + L                          | Clear log                      | Clear log                        |
| Ctrl + O                          | Open transaction file(s)       | Open specification file          |
| Ctrl + S                          | Save transaction(s) to file(s) | Backup current specification     |
| Ctrl + P                          | Print transaction              | -                                |
| Ctrl + T                          | Open new tab                   | -                                |
| Ctrl + PgDn /  Ctrl + Tab         | Next tab                       | -                                |
| Ctrl + PgUp /  Ctrl + Shift + Tab | Previous tab                   | -                                |
| Ctrl + F4                         | Close current tab              | -                                |
| Ctrl + Alt + Q                    | Quit SIGNAL                    | -                                |


# HTTP Transaction API

Signal has a built-in HTTP WEB API. The API allows for transaction management, configuration settings, and information 
gathering.

The API is supported by both the command-line and graphic user interfaces. It runs in a separate thread so that you
can use GUI along with API at the same time 

## Short API reference

| URL                                   | Method | Purpose                                                       | Headers required                 | URL params                                       | Body                                         |  
|---------------------------------------|--------|---------------------------------------------------------------|----------------------------------|--------------------------------------------------|----------------------------------------------|
| /api/documentation                    | `GET`  | Get user reference guide                                      | -                                | -                                                | -                                            |
| /api/transactions                     | `GET`  | Get data of all transactions made in the current runtime      | -                                | -                                                | -                                            |
| /api/transactions/{trans_id}          | `GET`  | Get data of specific transaction made in the current runtime  | -                                | trans_id: ID of previously-made transaction      | -                                            |
| /api/transactions                     | `POST` | Create new transaction                                        | Content-Type: application/json   | -                                                | Transaction                                  |
| /api/transactions/{trans_id}/reversal | `POST` | Reverse specific transaction made in the current runtime      | -                                | trans_id: ID of previously-made transaction      | -                                            |
| /transactions/{trans_type}            | `POST` | Create predefined transaction                                 | Content-Type: application/json   | TransType: Enum, see [data models](#data-models) | CardData                                     |
| /api/connection                       | `GET`  | Get connection object                                         | -                                | -                                                | -                                            |
| /api/connection/{action}              | `PUT`  | Perform connection action such as connect, disconnect, etc    | Content-Type: application/json   | action: Enum, see [data models](#data-models)    | Connection (optional) when action is connect |
| /api/config                           | `GET`  | Get current configuration object                              | -                                | -                                                | -                                            |
| /api/config                           | `PUT`  | Update current configuration object                           | Content-Type: application/json   | -                                                | Config                                       |
| /api/specification                    | `GET`  | Get specification object                                      | -                                | -                                                | -                                            |
| /api/tools/transactions/validate      | `POST` | Validate transaction                                          | Content-Type: application/json   | -                                                | Transaction                                  |

## Complete API reference

### Get API documentation

**Description**: Get a user reference guide. This method is more suitable for rendering in the browser to the end user

**Endpoint**: `GET /api/documentation`

**Request example**: `curl --location 'http://192.168.0.3:7777/api/documentation'`

**Response example**:

>>>>webpage


### Get transactions

**Description**: Get data of all transactions made in the current runtime

**Endpoint**: `GET /api/transactions`

**Request example**: `curl --location 'http://192.168.0.3:7777/api/transactions'`

**Response example**: 

>>>Transactions



   


## Data models

## Postman collection
Postman is an API platform for building and using APIs. Postman simplifies each step of the API lifecycle and 
streamlines collaboration so you can create better APIs faster. See more about it on 
the [Postman home page](https://www.postman.com/)

Signal Postman collection covers basic API usage. You can expand the collection, write the test-scenarios using 
this tool

Press <a href="c:/fedor/sv.event.example.zip" download> here </a> to download the latest Signal Postman collection 


# Command Line Interface
The SIGNAL can be run in Command Line Interface mode (CLI) by usage of specific flags `-c` or `--console`. In CLI mode 
GUI will not be run, all the output will be placed in the command line instead. CLI mode is useful when some external 
tool or script needs to send a transaction without the usage of GUI. The CLI mode targets simplified integration for the 
ISO test system

The console-mode flag `-c` or `--console` is required to run CLI mode (see [examples](#cli-examples)). In case of the 
absence of console-mode flags GUI mode will be run by default

Flags `-h` or `--help` `--about` do not require console-mode flags

## CLI Usage

**Important**: The Windows command line does not support combinations of command line keys. Each key should be added 
separately

For example, the following incorrect command will return an error, while the correct one will work as expected

 | Correct                 | Incorrect           |
 |-------------------------|---------------------|
 | `signal.exe -c -r -i 2` | `signal.exe -cri 2` |


It is recommended to use long keys like `--console` instead of `-c`, `--repeat` instead of `-r`, and so on. The short 
keys do the same, but such commands are not easy to read and the scenario is not always transparent 


To see usage hint call 
> signal.exe --help

```text
usage: _signal.py [-h] -c [-f FILE] [-d DIR] [-a ADDRESS] [-p PORT] [-r] [--log-file LOG_FILE] [-l LOG_LEVEL] [-i INTERVAL] [--parallel] [-t TIMEOUT] [--about] [-e] [--default] [-v] [--print-config] [--config-file CONFIG_FILE]
                  [--api-mode]

SIGNAL v0.19

options:
  -h, --help            show this help message and exit
  -c, --console         Run SIGNAL in Command Line Interface mode
  -f FILE, --file FILE  File or file-mask to parse
  -d DIR, --dir DIR     Directory with files to parse. SIGNAL will try all of the files from the directory
  -a ADDRESS, --address ADDRESS
                        Host TCP/IP address
  -p PORT, --port PORT  TCP/IP port to connect
  -r, --repeat          Repeat transactions after sending
  --log-file LOG_FILE   Set log file path. Default common/log/signal.log
  -l LOG_LEVEL, --log-level LOG_LEVEL
                        Debug level: DEBUG, INFO, WARNING, ERROR, CRITICAL, NOTSET
  -i INTERVAL, --interval INTERVAL
                        Wait (seconds) before send next transaction
  --parallel            Send new transaction with no waiting of answer for previous one
  -t TIMEOUT, --timeout TIMEOUT
                        Timeout of waiting resp
  --about               Show info about the SIGNAL
  -e, --echo-test       Send echo-test
  --default             Send default transaction message
  -v, --version         Print current version of SIGNAL
  --print-config        Print configuration parameters
  --config-file CONFIG_FILE
                        Set configuration file path
  --api-mode            Run signal in API mode
```

## CLI examples

Using the command line interface, you can write flexible transaction test scenarios. Below are a few examples of 
CLI commands. It is not a complete list of possible combinations. See [CLI Usage](#cli-Usage) to get all the commands

### Command examples

| Command                                                      | Action                                                                                    | 
|--------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| `signal.exe --console --default`                             | Send default transaction to the host                                                      |
| `signal.exe --console --echo-test`                           | Send echo-test to the host                                                                |
| `signal.exe --console --about`                               | Show info about the SIGNAL                                                                |
| `signal.exe --console --file /transactions/transaction.json` | Parse specific file `/transactions/transaction.json` and send the transaction to the host |
| `signal.exe --console --default --repeat --interval 2`       | Begin transaction loop, sending new transaction every 2 sec                               |
| `signal.exe --console --dir /transactions --parallel`        | Immediate send all the transactions from the directory /transactions                      |
| `signal.exe --console --api-mode`                            | Run Signal in console API mode                                                            |

## CLI output

In CLI mode SIGNAL prints the output at the console and to the log as well. The debug level can be set by `--log-level`
key, see [usage](#cli-Usage)

See examples of output below

<details>
 <summary>️signal.exe --console --about</summary>
 <p align="left">

```text
PS C:\signal> signal.exe --console --about
02:57:15 [INFO] 
02:57:15 [INFO]   ::::::::  :::::::::::  ::::::::   ::::    :::      :::      :::        
02:57:15 [INFO]  :+:    :+:     :+:     :+:    :+:  :+:+:   :+:    :+: :+:    :+:        
02:57:15 [INFO]  +:+            +:+     +:+         :+:+:+  +:+   +:+   +:+   +:+        
02:57:15 [INFO]  +#++:++#++     +#+     :#:         +#+ +:+ +#+  +#++:++#++:  +#+        
02:57:15 [INFO]         +#+     +#+     +#+   +#+#  +#+  +#+#+#  +#+     +#+  +#+        
02:57:15 [INFO]  #+#    #+#     #+#     #+#    #+#  #+#   #+#+#  #+#     #+#  #+#        
02:57:15 [INFO]   ########  ###########  ########   ###    ####  ###     ###  ########## 
02:57:15 [INFO] 
02:57:15 [INFO]   Simplified ISO generation algorithm v0.18
02:57:15 [INFO] 
02:57:15 [INFO]   Use only on test environment
02:57:15 [INFO] 
02:57:15 [INFO]   Version v0.18
02:57:15 [INFO] 
02:57:15 [INFO]   Released in May 2024
02:57:15 [INFO] 
02:57:15 [INFO]   Developed by Fedor Ivanov
02:57:15 [INFO] 
02:57:15 [INFO]   Contact fedornivanov@gmail.com
02:57:15 [INFO]
```
</p>
</details>

<details>
 <summary>signal.exe --console --echo-test</summary>
 <p align="left">
   
```text
PS C:\signal> signal.exe --console --echo-test 
03:05:12 [INFO] ## Running SIGNAL in Console mode ##
03:05:12 [INFO] Press CTRL+C to exit
03:05:12 [INFO] 
03:05:12 [INFO] 
03:05:12 [INFO] Processing file echo-test.json
03:05:12 [WARNING] Host disconnected. Trying to establish the connection
03:05:12 [INFO] Connection ESTABLISHED
03:05:12 [INFO] 
03:05:12 [INFO] [TRANS_ID][20240414_030512_8695314843]
03:05:12 [INFO] [MSG_TYPE][0800]
03:05:12 [INFO] [BITMAP  ][7, 11, 70]
03:05:12 [INFO] [007][010][0414030512]
03:05:12 [INFO] [011][006][615012]
03:05:12 [INFO] [070][003][301]
03:05:12 [INFO] 
03:05:12 [INFO] Outgoing transaction ID [20240414_030512_8695314843] sent
03:05:13 [INFO] Incoming transaction ID [20240414_030512_8695314843] received
03:05:13 [INFO]
03:05:13 [INFO] [TRANS_ID][20240414_030512_8695314843]
03:05:13 [INFO] [MSG_TYPE][0810]
03:05:13 [INFO] [BITMAP  ][7, 11, 39, 70]
03:05:13 [INFO] [007][010][0414030512]
03:05:13 [INFO] [011][006][615012]
03:05:13 [INFO] [039][002][00]
03:05:13 [INFO] [070][002][30]
03:05:13 [INFO]
03:05:13 [INFO] Transaction ID [20240414_030512_8695314843] matched, response time seconds: 1.082
```
</p>
</details>


<details>
 <summary>️signal.exe --console --print-config</summary>
 <p align="left">

```text
PS C:\signal> signal.exe --console --print-config 
17:01:33 [INFO] ## Configuration parameters ##
17:01:33 [INFO] 
17:01:33 [INFO] Path: common/data/settings/config.json
17:01:33 [INFO] 
17:01:33 [INFO] Data:
17:01:33 [INFO] {
17:01:33 [INFO]     "host": {
17:01:33 [INFO]         "host": "172.21.30.5",
17:01:33 [INFO]         "port": 16677,
17:01:33 [INFO]         "keep_alive_mode": false,
17:01:33 [INFO]         "keep_alive_interval": 300,
17:01:33 [INFO]         "header_length": 2,
17:01:33 [INFO]         "header_length_exists": true
17:01:33 [INFO]     },
17:01:33 [INFO]     "terminal": {
17:01:33 [INFO]         "process_default_dump": true,
17:01:33 [INFO]         "connect_on_startup": true,
17:01:33 [INFO]         "load_remote_spec": false
17:01:33 [INFO]     },
17:01:33 [INFO]     "debug": {
17:01:33 [INFO]         "level": "INFO",
17:01:33 [INFO]         "clear_log": true,
17:01:33 [INFO]         "parse_subfields": false,
17:01:33 [INFO]         "backup_storage_depth": 10
17:01:33 [INFO]     },
17:01:33 [INFO]     "validation": {
17:01:33 [INFO]         "validation_enabled": true,
17:01:33 [INFO]         "validate_window": true,
17:01:33 [INFO]         "validate_incoming": true,
17:01:33 [INFO]         "validate_outgoing": true,
17:01:33 [INFO]         "validation_mode": "WARNING"
17:01:33 [INFO]         "rewrite_local_spec": false,
17:01:33 [INFO]         "remote_spec_url": "http://172.21.30.20:4242/specification",
17:01:33 [INFO]         "backup_storage_depth": 30,
17:01:33 [INFO]         "backup_storage": false,
17:01:33 [INFO]         "manual_input_mode": false
17:01:33 [INFO]     }
17:01:33 [INFO] }
17:01:33 [INFO]
17:01:33 [INFO] ## End of configuration parameters ##
17:01:33 [INFO]
17:01:33 [INFO] ## Running SIGNAL in Console mode ##
17:01:33 [INFO] Press CTRL+C to exit

```
</p>
</details>


# Library re-usage

The Signal is built as a library of weakly connected modules. The modules can be used separately, allowing to develop or 
improve other solutions by the Signal package

The Signal uses the PyQt6 as a core even if the application does not have any GUI. Before usage, the modules refer to 
the [Resources](#resources) chapter and make an acquaintance with basic PyQt6 and Pydantic concepts. Otherwise, if you 
are already familiar with those packages, just go forth

## Requirements

Unlike GUI the Signal library requires you to install dependencies, defined in the "requirements.txt" file from the 
Signal's root directory. See the actual dependencies in the file, here are listed requirements, which are actually 
for Signal v0.18

The following dependencies are required to install to run the library

| Dependency                                                 | Version | Higher version allowed | 
|------------------------------------------------------------|---------|------------------------| 
| [Python](https://www.python.org/)                          | 3.12    | Yes                    |
| [PyQt6](https://wiki.python.org/moin/PyQt)                 | 6.6.1   | Yes                    |
| [Pydantic](https://pydantic.dev/)                          | 2.6.3   | Yes                    |
| [Flask](https://flask.palletsprojects.com/en/3.0.x/)       | 3.0.3   | Yes                    |
| [Flask-pydantic](https://pypi.org/project/Flask-Pydantic/) | 0.12.0  | Yes                    |



Refer to chapter [Library installation](#library-installation) to figure the dependencies installation process out

## Library installation

To install all the dependencies by one command change the directory to the Signal's root, make sure that the 
"requirements.txt" file exists in the directory, then run the following command. 

>pip install -r requirements.txt

It is also possible to read the file and install the modules manually

## Modules purpose
## Logging

## Modules usage example
This chapter describes the minimal working code example. It is highly recommended to use
[Python virtual environment](https://docs.python.org/3/library/venv.html) to run the application


### Preparation
To prepare for library usage first you have to create and activate the Python virtual environment then install all 
the dependencies

Create and activate Python virtual environment


>C:\signal> python -m venv C:\signal\signal_virtual_env    # Create a new virtual environment
> 
>C:\signal> C:\signal\signal_virtual_env\Scripts\activate  # Activate the virtual environment


Install the dependencies from requirements.txt into the virtual environment


> (signal_virtual_env) C:\signal> pip install -r requirements.txt


The preparation is finished, now is possible to run the [Code examples](#code-examples) 

### Code examples
The library can be used for its intended purpose, sending the ISO 8583 transactions

<details>
 <summary>️Minimal code example - send the single transaction from the default file</summary>

```python
from common.lib.data_models.Config import Config
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.core.Terminal import Terminal
from common.lib.data_models.Transaction import Transaction
from common.lib.core.FieldsGenerator import FieldsGenerator

"""
The Signal library minimal code example - sends the single transaction from the default file

This script does not run QApplication and QEventLoop. Due to that, the script cannot wait for the answer, also the 
signal-slot model cannot be used

The code examples is ready to begin without any changes
"""

# Create Config object. The Config is a crucial data object, contains basic settings for all the application
config: Config = Config.parse_file(TermFilesPath.CONFIG)
# After the config is created you can set the parameters as you prefer
# e.g.: config.host.port = 16677 and so on

# The Terminal - core of the application, which will be used for sending the transaction
terminal: Terminal = Terminal(config)

# This object will update transaction fields to avoid transaction duplicates
data_generator = FieldsGenerator()

# Parse default transaction file
transaction: Transaction = Transaction.parse_file(TermFilesPath.DEFAULT_FILE)

# Update fields dynamic values such as ID, date and so on
transaction: Transaction = data_generator.set_generated_fields(transaction)

# Send the previously-made transaction to the host
terminal.send(transaction)

# exit
```

</details>

<details>
 <summary>More complex example, with usage PyQt6 features, logging, and so on</summary>

```python
from PyQt6.QtCore import QCoreApplication, QTimer
from common.lib.data_models.Config import Config
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.core.Terminal import Terminal
from common.lib.data_models.Transaction import Transaction
from common.lib.core.FieldsGenerator import FieldsGenerator
from common.lib.core.Logger import Logger

"""
A bit more complex example, with usage PyQt6 features, logging, and so on

This script not runs QApplication and QEventLoop. Due to that, the script will wait for the answer, also the 
signal-slot model can be used
 
This example illustrates the creation of the PyQt application, which is run and ready for interaction in PyQt style

The code examples is ready to begin without any changes
"""

# The objects preparation

# In case when your solution does not use GUI it is required to create QCoreApplication and set in on the Terminal
application = QCoreApplication([])  # Create the Signal PyQt application

# Create Config object. The Config is a crucial data object, contains basic settings for all the application
config: Config = Config.parse_file(TermFilesPath.CONFIG)
# After the config is created you can set the parameters as you prefer
# e.g.: config.host.port = 16677 and so on

# The Terminal - core of the application, which will be used for sending the transaction
terminal: Terminal = Terminal(config=config, application=application)  # Send previously-made QCoreApplication

# Set the default screen logger up
Logger().create_logger()

# This object will update transaction fields to avoid transaction duplicates
data_generator = FieldsGenerator()

# Parse default transaction file
transaction: Transaction = Transaction.parse_file(TermFilesPath.DEFAULT_FILE)

# Update fields dynamic values such as ID, date and so on
transaction: Transaction = data_generator.set_generated_fields(transaction)


# Create a delayed start timer. This workaround will help to begin the task after the application is started
timer = QTimer()  # This timer will be processed in QEventloop right after the application is executed
timer.setSingleShot(True)  # It signals once the application start
timer.timeout.connect(lambda: terminal.send(transaction))  # Transaction will be one of the first events
timer.start(0)  # Signals timeout immediately


# Finally run the application, which begin the QEventloop and send the transaction
# Due to the part below the application proceed to work, processing PyQt events and signals
terminal.run()  # Run the QCoreApplication
```
</details>

Also, the modules can be valuable in ISO 8583 transaction data processing, without sending the transaction

<details>
 <summary>Generate transaction data-dumps</summary>
</details>

<details>
 <summary>Convert complicated data-dump files to useful JSON representation</summary>
</details>

<details>
 <summary>Validate transaction data files</summary>
</details>


In this chapter, only the basic possibilities of the Signal library were illustrated. There are a huge amount of other 
options to use the Signal's library as a transactional generator or transactions data processing tool


## Compilation of executable binary

## Recommendations


# Data models

The signal uses [Pydantic](https://docs.pydantic.dev/latest/) data models to manipulate the data. The signal uses 
Pydantic data models to manipulate the data. This chapter described the main data models, their requirements, 
and validations

## Transaction

## Config

## Specification


# Specification settings

## Specification Overview

This chapter describes the specification settings and maintenance. Refer to SVFE E-pay specification for more info.

The Specification is a root data structure, describing data processing mechanics, such as fields hierarchy, types, 
validation, and other things. SIGNAL needs the correct settings in the Specification for regular work. From v0.15 
specification settings are required for transaction processing.

The specification can be set using the button "Specification" of MainWindow. Settings through GUI are highly recommended 
by the author. 


## Settings description

![image](https://i.imgur.com/Wvg8EuX.png)

The table below describes the settings window columns from left to right

| Field       | Purpose                                                                                                                                                                                                                                                | Used to                                                      | Type                       | Mandatory    |
|-------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------|----------------------------|--------------|
| Field       | The field or subfield number                                                                                                                                                                                                                           | Define main fields structure, describe fields nesting        | Number                     | Yes          |
| Description | Free text field purpose explanation                                                                                                                                                                                                                    | Show field description on MainWindow transaction constructor | Text, no min or max length | No           |
| Min Len     | Field value minimum length                                                                                                                                                                                                                             | Fields validation during data processing                     | Number, min value is 1     | Yes          |
| Max Len     | Field value maximum length                                                                                                                                                                                                                             | Fields validation during data processing                     | Number, min value is 1     | Yes          | 
| Data Len    | Applicable for variable-length fields. This means count numbers mark the field's own length. Should be taken from the E-pay specification document. In the specification usually marks as `LLVAR` - 2 digits, `LLLVAR` - 3 digits, and so on           | Message construction, Fields validation, Message parsing     | Number, min value is 0     | Yes          |
| Tag Len     | For complex fields only (field should contain subfields). This means count numbers mark. In the specification usually marked as `LLVAR` - 2 digits, `LLLVAR` - 3 digits, and so on. Tag Len of the field should be equal to the field's own Data Len   | Message construction, Fields validation, Message parsing     | Number, min value is 0     | Yes          |
| Alpha       | Are the alphabetic letters allowed in this field                                                                                                                                                                                                       | Fields validation                                            | Checkbox                   | Yes          |
| Numeric     | Are the digits  allowed in this field                                                                                                                                                                                                                  | Fields validation                                            | Checkbox                   | Yes          |
| Special     | Are the special characters allowed in this field                                                                                                                                                                                                       | Fields validation                                            | Checkbox                   | Yes          |
| Matching    | If yes the field will be used for matching requests and responses. It means SIGNAL, sending the transaction expects the same field value in the SV response                                                                                            | Message matching                                             | Checkbox                   | Yes          |
| Reversal    | When Yes then the field value will be taken from the original message and put to the reversal in case of reversal                                                                                                                                      | Message matching, message construction                       | Checkbox                   | Yes          |
| Generated   | Can the fields be auto-generated by SIGNAL before sending? If yes then the corresponding checkbox appears in Main Window¹                                                                                                                              | Message construction                                         | Checkbox                   | Yes          |
| Secret      | If yes field value will be hidden in the log, transaction constructor, and on MainWindow display³                                                                                                                                                      | Display data, log writing                                    | Checkbox                   | Yes          |

¹ Currently, SIGNAL supports randomly generated field values only. No date-time and other specific format are supported, except pre-defined fields 7 and 11

² Due to security reasons, it is impossible to set Primary Account Number (Field 2) as non-secret. The field has a non-removable "secret" mark  

## Specification backup

## Remote specification
The local specification `JSON` file always is at the path `common/data/settings/specification.json`, however, SIGNAL can get general specification `JSON` remotely on the startup stage and by the user's request in SpecWindow. The specification URL should be set in the settings. In case when the remote specification is set by settings but the SIGNAL is unable to get remote specification data the local spec data will be taken instead from the "settings" directory

SIGNAL can get general specification JSON remotely on the startup stage and by the user's request in SpecWindow. The specification URL should be set in the settings.

In general, the specification endpoint has to return the Spec JSON by GET request without any additional actions

The conditions for the remote spec endpoint:


* Be available when SIGNAL starts
  * Support GET requests with no additional actions
  * Respond by HTTP-status 200
  * Send header "Content-type": "application/json" in the response
  * Return valid specification data in response-body


## Remote specification endpoint setting

The following [code](#remote-spec-endpoint-code-example) illustrates the endpoint example. In this example, endpoint http://127.0.0.1:4242/specification returns specification file data `/opt/spec/specification.json`

  
**To begin remote specification endpoint**

1. Prepare specification.json file. You can get it from the directory `common/data/settings` or save a copy using SpecWindow which executes by button `Specification` on the MainWindow 
   2. Prepare file `signal_spec.py`, containing [endpoint script](#remote-spec-endpoint-code-example)
   3. Set `SERVER_ADDRESS`, `PORT`, `FILE` parameters in the file `signal_spec.py`
   4. Put both files `specification.json` and `signal_spec.py` to remote server
   5. Run the code using command `nohup python signal_spec.py &`
   6. For checking open specified URL in browser, it should show the specification `JSON`. In example below the URL is http://127.0.0.1:4242/specification


**Test of remote specification endpoint**

![image](https://i.imgur.com/ahgkMdS.png)


## Remote spec endpoint code example

```python
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer

"""
Basic realization of SIGNAL Specification remote endpoint. This endpoint returns specification.json by GET request

Check and set the required configuration parameters below before run 

Was tested on Python3 only
"""

SERVER_ADDRESS = '127.0.0.1'  # The address of the server machine
PORT = 4242  # Port for incoming connection
PATH = '/specification'  # URL path to get the specification file
FILE = '/opt/spec/specification.json'  # The Specification file path, the file should be returned by GET request

# By these settings we create URL http://127.0.0.1:4242/specification which returns file /opt/spec/specification.json

class HttpSpec(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != PATH:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        with open(FILE) as json_file:
            self.wfile.write(json_file.read().encode())


server = HTTPServer((SERVER_ADDRESS, PORT), HttpSpec)

try:
    server.serve_forever()
except KeyboardInterrupt:
    pass

server.server_close()
```
# Fields validation
## Main validation
## Extended validation
## Violation mode
## Directions
## Complex fields representation
## Manual entry mode


# Configuration
## Config overview
## Config file
## Settings
## Remote host
## Specification
## On startup
## Log
## Validation
## Fields


# Transaction data files


## Data files overview

The SIGNAL supports multiple representations of transaction data files. The data can be put to the SIGNAL using 
one of three formats - `JSON`, `INI`, and `DUMP`. The data is stored in text files, which can be read or written 
by SIGNAL. This chapter describes each format's features and purpose

## The data formats description

| Format | File extension | Incoming  | Outgoing | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
|--------|----------------|-----------|----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| JSON   | `.json`        | Yes       | Yes      | Equally well suited for operator reading and machine analysis. The main goal is to make complex fields not so complicated, through structure-readable decomposition. Fields and subfield lengths are left out because they will be calculated later according to the Specification. All the transactions, incoming and outgoing stored in memory in JSON representation. Strictly requires Specification settings for each subfield                                                            | 
| INI    | `.ini`         | Yes       | Yes      | Flat format, where each field is written in one string. Fields fill in Tag-Length-Value (TLV) style with no separators. All the lengths have to be calculated and set by the operator. The format skips the data validation process. Recommended when you definitely understand what you do. Requires specification for top-level fields only, subfields specification is not required                                                                                                         | 
| DUMP   | `.dmp`         | Yes       | Yes      | Raw SV-dump format. Used for loading and generating SVFE-compatible dump messages for parsing incoming and generating outgoing SV messages. Low-level data exchange with SVFE makes using this format. The DUMP is the fully ready-read message for the SVFE epayint module. For the sv-dump building recommended setting field data through the transaction constructor using JSON or INI style, then generate the dump by SIGNAL interface. Manual analysis or generation is not recommended | 

## Loading to the SIGNAL

To read the incoming data file in the open SIGNAL window press `CTRL + O`, or hit the button "Parse file" on the 
MainWindow bottom, then choose the file using the file-navigation window. SIGNAL recognizes the incoming file format 
by file extension. When the extension is absent or unknown the SIGNAL will try to parse the file using each format 
pattern one by one. Better to set the correct extension for each format. Refer to the
[data formats description](#the-data-formats-description) to define the correct extension for each file format

## Save transaction to file

... 

# Data storage
## Default messages
## Dictionaries
## License info
## Settings storage
## Specification backup

# Logging
## Log levels
## Storage and rotation
## Hide secrets

# Bugs
## List of known bugs

| Bug                                                           | Status  | Workaround                                                                          | Comment                                                            |  
|---------------------------------------------------------------|---------|-------------------------------------------------------------------------------------|--------------------------------------------------------------------|
| Console window appears when I run GUI                         | Active  | Set Terminal app to default to "Windows Console Host" instead of "Windows Terminal" | [Solution](https://github.com/pyinstaller/pyinstaller/issues/8022) |
| No data in Connector when no such field in the specification  | Active  | -                                                                                   | -                                                                  | 
| Sending Field 62 I get Format Error (RC=30) in response       | Active  | Fill the field data manually in flat mode                                           | -                                                                  |


# About SIGNAL

The text version of Signal's logo

```text
  ::::::::  :::::::::::  ::::::::   ::::    :::      :::      :::        
 :+:    :+:     :+:     :+:    :+:  :+:+:   :+:    :+: :+:    :+:        
 +:+            +:+     +:+         :+:+:+  +:+   +:+   +:+   +:+        
 +#++:++#++     +#+     :#:         +#+ +:+ +#+  +#++:++#++:  +#+        
        +#+     +#+     +#+   +#+#  +#+  +#+#+#  +#+     +#+  +#+        
 #+#    #+#     #+#     #+#    #+#  #+#   #+#+#  #+#     #+#  #+#        
  ########  ###########  ########   ###    ####  ###     ###  ########## 

  Simplified ISO generation algorithm v0.18 | Released in May 2024
```

## Concept

The main idea behind Signal is to make simple things easy to do. It targets to simplification of complicated everyday 
tasks when a part of your job is ISO 8583 OLTP service

SIGNAL is not an emulator of PSP or SmartVista. It doesn't try to be similar to these systems. It is more positioned as 
a simplified version card payment terminal, developed with respect for the everyday needs of the Card Processing Support 
Team

Written on Python 3.12 with the use of [PyQt6](https://doc.qt.io/) and [Pydantic](https://docs.pydantic.dev/latest/) 
packages

## License

SIGNAL is distributed under the GNU/GPL license as free software. Using SIGNAL you have to accept the license agreement

See more on [GNU licence page](https://www.gnu.org/licenses/) and 
[free software Wiki article](https://en.wikipedia.org/wiki/Free_software) in the [resources](#resources) chapter

Long story short: the SIGNAL is free for any purpose, excluding selling it. Sales are strictly prohibited. 
Contact the [author](#author) in case of any copyright questions

<details>
 <summary>️GNU/GPL license agreement</summary>
<p>

     GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007
     
     Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
     Everyone is permitted to copy and distribute verbatim copies
     of this license document, but changing it is not allowed.

                                Preamble

      The GNU General Public License is a free, copyleft license for
    software and other kinds of works.

      The licenses for most software and other practical works are designed
    to take away your freedom to share and change the works.  By contrast,
    the GNU General Public License is intended to guarantee your freedom to
    share and change all versions of a program--to make sure it remains free
    software for all its users.  We, the Free Software Foundation, use the
    GNU General Public License for most of our software; it applies also to
    any other work released this way by its authors.  You can apply it to
    your programs, too.

      When we speak of free software, we are referring to freedom, not
    price.  Our General Public Licenses are designed to make sure that you
    have the freedom to distribute copies of free software (and charge for
    them if you wish), that you receive source code or can get it if you
    want it, that you can change the software or use pieces of it in new
    free programs, and that you know you can do these things.

      To protect your rights, we need to prevent others from denying you
    these rights or asking you to surrender the rights.  Therefore, you have
    certain responsibilities if you distribute copies of the software, or if
    you modify it: responsibilities to respect the freedom of others.

      For example, if you distribute copies of such a program, whether
    gratis or for a fee, you must pass on to the recipients the same
    freedoms that you received.  You must make sure that they, too, receive
    or can get the source code.  And you must show them these terms so they
    know their rights.

      Developers that use the GNU GPL protect your rights with two steps:
    (1) assert copyright on the software, and (2) offer you this License
    giving you legal permission to copy, distribute and/or modify it.

      For the developers' and authors' protection, the GPL clearly explains
    that there is no warranty for this free software.  For both users' and
    authors' sake, the GPL requires that modified versions be marked as
    changed, so that their problems will not be attributed erroneously to
    authors of previous versions.

      Some devices are designed to deny users access to install or run
    modified versions of the software inside them, although the manufacturer
    can do so.  This is fundamentally incompatible with the aim of
    protecting users' freedom to change the software.  The systematic
    pattern of such abuse occurs in the area of products for individuals to
    use, which is precisely where it is most unacceptable.  Therefore, we
    have designed this version of the GPL to prohibit the practice for those
    products.  If such problems arise substantially in other domains, we
    stand ready to extend this provision to those domains in future versions
    of the GPL, as needed to protect the freedom of users.

      Finally, every program is threatened constantly by software patents.
    States should not allow patents to restrict development and use of
    software on general-purpose computers, but in those that do, we wish to
    avoid the special danger that patents applied to a free program could
    make it effectively proprietary.  To prevent this, the GPL assures that
    patents cannot be used to render the program non-free.

      The precise terms and conditions for copying, distribution and
    modification follow.

                           TERMS AND CONDITIONS

      0. Definitions.

      "This License" refers to version 3 of the GNU General Public License.

      "Copyright" also means copyright-like laws that apply to other kinds of
    works, such as semiconductor masks.

      "The Program" refers to any copyrightable work licensed under this
    License.  Each licensee is addressed as "you".  "Licensees" and
    "recipients" may be individuals or organizations.

      To "modify" a work means to copy from or adapt all or part of the work
    in a fashion requiring copyright permission, other than the making of an
    exact copy.  The resulting work is called a "modified version" of the
    earlier work or a work "based on" the earlier work.

      A "covered work" means either the unmodified Program or a work based
    on the Program.

      To "propagate" a work means to do anything with it that, without
    permission, would make you directly or secondarily liable for
    infringement under applicable copyright law, except executing it on a
    computer or modifying a private copy.  Propagation includes copying,
    distribution (with or without modification), making available to the
    public, and in some countries other activities as well.

      To "convey" a work means any kind of propagation that enables other
    parties to make or receive copies.  Mere interaction with a user through
    a computer network, with no transfer of a copy, is not conveying.

      An interactive user interface displays "Appropriate Legal Notices"
    to the extent that it includes a convenient and prominently visible
    feature that (1) displays an appropriate copyright notice, and (2)
    tells the user that there is no warranty for the work (except to the
    extent that warranties are provided), that licensees may convey the
    work under this License, and how to view a copy of this License.  If
    the interface presents a list of user commands or options, such as a
    menu, a prominent item in the list meets this criterion.

      1. Source Code.

      The "source code" for a work means the preferred form of the work
    for making modifications to it.  "Object code" means any non-source
    form of a work.

      A "Standard Interface" means an interface that either is an official
    standard defined by a recognized standards body, or, in the case of
    interfaces specified for a particular programming language, one that
    is widely used among developers working in that language.

      The "System Libraries" of an executable work include anything, other
    than the work as a whole, that (a) is included in the normal form of
    packaging a Major Component, but which is not part of that Major
    Component, and (b) serves only to enable use of the work with that
    Major Component, or to implement a Standard Interface for which an
    implementation is available to the public in source code form.  A
    "Major Component", in this context, means a major essential component
    (kernel, window system, and so on) of the specific operating system
    (if any) on which the executable work runs, or a compiler used to
    produce the work, or an object code interpreter used to run it.

      The "Corresponding Source" for a work in object code form means all
    the source code needed to generate, install, and (for an executable
    work) run the object code and to modify the work, including scripts to
    control those activities.  However, it does not include the work's
    System Libraries, or general-purpose tools or generally available free
    programs which are used unmodified in performing those activities but
    which are not part of the work.  For example, Corresponding Source
    includes interface definition files associated with source files for
    the work, and the source code for shared libraries and dynamically
    linked subprograms that the work is specifically designed to require,
    such as by intimate data communication or control flow between those
    subprograms and other parts of the work.

      The Corresponding Source need not include anything that users
    can regenerate automatically from other parts of the Corresponding
    Source.

      The Corresponding Source for a work in source code form is that
    same work.

      2. Basic Permissions.

      All rights granted under this License are granted for the term of
    copyright on the Program, and are irrevocable provided the stated
    conditions are met.  This License explicitly affirms your unlimited
    permission to run the unmodified Program.  The output from running a
    covered work is covered by this License only if the output, given its
    content, constitutes a covered work.  This License acknowledges your
    rights of fair use or other equivalent, as provided by copyright law.

      You may make, run and propagate covered works that you do not
    convey, without conditions so long as your license otherwise remains
    in force.  You may convey covered works to others for the sole purpose
    of having them make modifications exclusively for you, or provide you
    with facilities for running those works, provided that you comply with
    the terms of this License in conveying all material for which you do
    not control copyright.  Those thus making or running the covered works
    for you must do so exclusively on your behalf, under your direction
    and control, on terms that prohibit them from making any copies of
    your copyrighted material outside their relationship with you.

      Conveying under any other circumstances is permitted solely under
    the conditions stated below.  Sublicensing is not allowed; section 10
    makes it unnecessary.

      3. Protecting Users' Legal Rights From Anti-Circumvention Law.

      No covered work shall be deemed part of an effective technological
    measure under any applicable law fulfilling obligations under article
    11 of the WIPO copyright treaty adopted on 20 December 1996, or
    similar laws prohibiting or restricting circumvention of such
    measures.

      When you convey a covered work, you waive any legal power to forbid
    circumvention of technological measures to the extent such circumvention
    is effected by exercising rights under this License with respect to
    the covered work, and you disclaim any intention to limit operation or
    modification of the work as a means of enforcing, against the work's
    users, your or third parties' legal rights to forbid circumvention of
    technological measures.

      4. Conveying Verbatim Copies.

      You may convey verbatim copies of the Program's source code as you
    receive it, in any medium, provided that you conspicuously and
    appropriately publish on each copy an appropriate copyright notice;
    keep intact all notices stating that this License and any
    non-permissive terms added in accord with section 7 apply to the code;
    keep intact all notices of the absence of any warranty; and give all
    recipients a copy of this License along with the Program.

      You may charge any price or no price for each copy that you convey,
    and you may offer support or warranty protection for a fee.

      5. Conveying Modified Source Versions.

      You may convey a work based on the Program, or the modifications to
    produce it from the Program, in the form of source code under the
    terms of section 4, provided that you also meet all of these conditions:

        a) The work must carry prominent notices stating that you modified
        it, and giving a relevant date.

        b) The work must carry prominent notices stating that it is
        released under this License and any conditions added under section
        7.  This requirement modifies the requirement in section 4 to
        "keep intact all notices".

        c) You must license the entire work, as a whole, under this
        License to anyone who comes into possession of a copy.  This
        License will therefore apply, along with any applicable section 7
        additional terms, to the whole of the work, and all its parts,
        regardless of how they are packaged.  This License gives no
        permission to license the work in any other way, but it does not
        invalidate such permission if you have separately received it.

        d) If the work has interactive user interfaces, each must display
        Appropriate Legal Notices; however, if the Program has interactive
        interfaces that do not display Appropriate Legal Notices, your
        work need not make them do so.

      A compilation of a covered work with other separate and independent
    works, which are not by their nature extensions of the covered work,
    and which are not combined with it such as to form a larger program,
    in or on a volume of a storage or distribution medium, is called an
    "aggregate" if the compilation and its resulting copyright are not
    used to limit the access or legal rights of the compilation's users
    beyond what the individual works permit.  Inclusion of a covered work
    in an aggregate does not cause this License to apply to the other
    parts of the aggregate.

      6. Conveying Non-Source Forms.

      You may convey a covered work in object code form under the terms
    of sections 4 and 5, provided that you also convey the
    machine-readable Corresponding Source under the terms of this License,
    in one of these ways:

        a) Convey the object code in, or embodied in, a physical product
        (including a physical distribution medium), accompanied by the
        Corresponding Source fixed on a durable physical medium
        customarily used for software interchange.

        b) Convey the object code in, or embodied in, a physical product
        (including a physical distribution medium), accompanied by a
        written offer, valid for at least three years and valid for as
        long as you offer spare parts or customer support for that product
        model, to give anyone who possesses the object code either (1) a
        copy of the Corresponding Source for all the software in the
        product that is covered by this License, on a durable physical
        medium customarily used for software interchange, for a price no
        more than your reasonable cost of physically performing this
        conveying of source, or (2) access to copy the
        Corresponding Source from a network server at no charge.

        c) Convey individual copies of the object code with a copy of the
        written offer to provide the Corresponding Source.  This
        alternative is allowed only occasionally and noncommercially, and
        only if you received the object code with such an offer, in accord
        with subsection 6b.

        d) Convey the object code by offering access from a designated
        place (gratis or for a charge), and offer equivalent access to the
        Corresponding Source in the same way through the same place at no
        further charge.  You need not require recipients to copy the
        Corresponding Source along with the object code.  If the place to
        copy the object code is a network server, the Corresponding Source
        may be on a different server (operated by you or a third party)
        that supports equivalent copying facilities, provided you maintain
        clear directions next to the object code saying where to find the
        Corresponding Source.  Regardless of what server hosts the
        Corresponding Source, you remain obligated to ensure that it is
        available for as long as needed to satisfy these requirements.

        e) Convey the object code using peer-to-peer transmission, provided
        you inform other peers where the object code and Corresponding
        Source of the work are being offered to the general public at no
        charge under subsection 6d.

      A separable portion of the object code, whose source code is excluded
    from the Corresponding Source as a System Library, need not be
    included in conveying the object code work.

      A "User Product" is either (1) a "consumer product", which means any
    tangible personal property which is normally used for personal, family,
    or household purposes, or (2) anything designed or sold for incorporation
    into a dwelling.  In determining whether a product is a consumer product,
    doubtful cases shall be resolved in favor of coverage.  For a particular
    product received by a particular user, "normally used" refers to a
    typical or common use of that class of product, regardless of the status
    of the particular user or of the way in which the particular user
    actually uses, or expects or is expected to use, the product.  A product
    is a consumer product regardless of whether the product has substantial
    commercial, industrial or non-consumer uses, unless such uses represent
    the only significant mode of use of the product.

      "Installation Information" for a User Product means any methods,
    procedures, authorization keys, or other information required to install
    and execute modified versions of a covered work in that User Product from
    a modified version of its Corresponding Source.  The information must
    suffice to ensure that the continued functioning of the modified object
    code is in no case prevented or interfered with solely because
    modification has been made.

      If you convey an object code work under this section in, or with, or
    specifically for use in, a User Product, and the conveying occurs as
    part of a transaction in which the right of possession and use of the
    User Product is transferred to the recipient in perpetuity or for a
    fixed term (regardless of how the transaction is characterized), the
    Corresponding Source conveyed under this section must be accompanied
    by the Installation Information.  But this requirement does not apply
    if neither you nor any third party retains the ability to install
    modified object code on the User Product (for example, the work has
    been installed in ROM).

      The requirement to provide Installation Information does not include a
    requirement to continue to provide support service, warranty, or updates
    for a work that has been modified or installed by the recipient, or for
    the User Product in which it has been modified or installed.  Access to a
    network may be denied when the modification itself materially and
    adversely affects the operation of the network or violates the rules and
    protocols for communication across the network.

      Corresponding Source conveyed, and Installation Information provided,
    in accord with this section must be in a format that is publicly
    documented (and with an implementation available to the public in
    source code form), and must require no special password or key for
    unpacking, reading or copying.

      7. Additional Terms.

      "Additional permissions" are terms that supplement the terms of this
    License by making exceptions from one or more of its conditions.
    Additional permissions that are applicable to the entire Program shall
    be treated as though they were included in this License, to the extent
    that they are valid under applicable law.  If additional permissions
    apply only to part of the Program, that part may be used separately
    under those permissions, but the entire Program remains governed by
    this License without regard to the additional permissions.

      When you convey a copy of a covered work, you may at your option
    remove any additional permissions from that copy, or from any part of
    it.  (Additional permissions may be written to require their own
    removal in certain cases when you modify the work.)  You may place
    additional permissions on material, added by you to a covered work,
    for which you have or can give appropriate copyright permission.

      Notwithstanding any other provision of this License, for material you
    add to a covered work, you may (if authorized by the copyright holders of
    that material) supplement the terms of this License with terms:

        a) Disclaiming warranty or limiting liability differently from the
        terms of sections 15 and 16 of this License; or

        b) Requiring preservation of specified reasonable legal notices or
        author attributions in that material or in the Appropriate Legal
        Notices displayed by works containing it; or

        c) Prohibiting misrepresentation of the origin of that material, or
        requiring that modified versions of such material be marked in
        reasonable ways as different from the original version; or

        d) Limiting the use for publicity purposes of names of licensors or
        authors of the material; or

        e) Declining to grant rights under trademark law for use of some
        trade names, trademarks, or service marks; or

        f) Requiring indemnification of licensors and authors of that
        material by anyone who conveys the material (or modified versions of
        it) with contractual assumptions of liability to the recipient, for
        any liability that these contractual assumptions directly impose on
        those licensors and authors.

      All other non-permissive additional terms are considered "further
    restrictions" within the meaning of section 10.  If the Program as you
    received it, or any part of it, contains a notice stating that it is
    governed by this License along with a term that is a further
    restriction, you may remove that term.  If a license document contains
    a further restriction but permits relicensing or conveying under this
    License, you may add to a covered work material governed by the terms
    of that license document, provided that the further restriction does
    not survive such relicensing or conveying.

      If you add terms to a covered work in accord with this section, you
    must place, in the relevant source files, a statement of the
    additional terms that apply to those files, or a notice indicating
    where to find the applicable terms.

      Additional terms, permissive or non-permissive, may be stated in the
    form of a separately written license, or stated as exceptions;
    the above requirements apply either way.

      8. Termination.

      You may not propagate or modify a covered work except as expressly
    provided under this License.  Any attempt otherwise to propagate or
    modify it is void, and will automatically terminate your rights under
    this License (including any patent licenses granted under the third
    paragraph of section 11).

      However, if you cease all violation of this License, then your
    license from a particular copyright holder is reinstated (a)
    provisionally, unless and until the copyright holder explicitly and
    finally terminates your license, and (b) permanently, if the copyright
    holder fails to notify you of the violation by some reasonable means
    prior to 60 days after the cessation.

      Moreover, your license from a particular copyright holder is
    reinstated permanently if the copyright holder notifies you of the
    violation by some reasonable means, this is the first time you have
    received notice of violation of this License (for any work) from that
    copyright holder, and you cure the violation prior to 30 days after
    your receipt of the notice.

      Termination of your rights under this section does not terminate the
    licenses of parties who have received copies or rights from you under
    this License.  If your rights have been terminated and not permanently
    reinstated, you do not qualify to receive new licenses for the same
    material under section 10.

      9. Acceptance Not Required for Having Copies.

      You are not required to accept this License in order to receive or
    run a copy of the Program.  Ancillary propagation of a covered work
    occurring solely as a consequence of using peer-to-peer transmission
    to receive a copy likewise does not require acceptance.  However,
    nothing other than this License grants you permission to propagate or
    modify any covered work.  These actions infringe copyright if you do
    not accept this License.  Therefore, by modifying or propagating a
    covered work, you indicate your acceptance of this License to do so.

      10. Automatic Licensing of Downstream Recipients.

      Each time you convey a covered work, the recipient automatically
    receives a license from the original licensors, to run, modify and
    propagate that work, subject to this License.  You are not responsible
    for enforcing compliance by third parties with this License.

      An "entity transaction" is a transaction transferring control of an
    organization, or substantially all assets of one, or subdividing an
    organization, or merging organizations.  If propagation of a covered
    work results from an entity transaction, each party to that
    transaction who receives a copy of the work also receives whatever
    licenses to the work the party's predecessor in interest had or could
    give under the previous paragraph, plus a right to possession of the
    Corresponding Source of the work from the predecessor in interest, if
    the predecessor has it or can get it with reasonable efforts.

      You may not impose any further restrictions on the exercise of the
    rights granted or affirmed under this License.  For example, you may
    not impose a license fee, royalty, or other charge for exercise of
    rights granted under this License, and you may not initiate litigation
    (including a cross-claim or counterclaim in a lawsuit) alleging that
    any patent claim is infringed by making, using, selling, offering for
    sale, or importing the Program or any portion of it.

      11. Patents.

      A "contributor" is a copyright holder who authorizes use under this
    License of the Program or a work on which the Program is based.  The
    work thus licensed is called the contributor's "contributor version".

      A contributor's "essential patent claims" are all patent claims
    owned or controlled by the contributor, whether already acquired or
    hereafter acquired, that would be infringed by some manner, permitted
    by this License, of making, using, or selling its contributor version,
    but do not include claims that would be infringed only as a
    consequence of further modification of the contributor version.  For
    purposes of this definition, "control" includes the right to grant
    patent sublicenses in a manner consistent with the requirements of
    this License.

      Each contributor grants you a non-exclusive, worldwide, royalty-free
    patent license under the contributor's essential patent claims, to
    make, use, sell, offer for sale, import and otherwise run, modify and
    propagate the contents of its contributor version.

      In the following three paragraphs, a "patent license" is any express
    agreement or commitment, however denominated, not to enforce a patent
    (such as an express permission to practice a patent or covenant not to
    sue for patent infringement).  To "grant" such a patent license to a
    party means to make such an agreement or commitment not to enforce a
    patent against the party.

      If you convey a covered work, knowingly relying on a patent license,
    and the Corresponding Source of the work is not available for anyone
    to copy, free of charge and under the terms of this License, through a
    publicly available network server or other readily accessible means,
    then you must either (1) cause the Corresponding Source to be so
    available, or (2) arrange to deprive yourself of the benefit of the
    patent license for this particular work, or (3) arrange, in a manner
    consistent with the requirements of this License, to extend the patent
    license to downstream recipients.  "Knowingly relying" means you have
    actual knowledge that, but for the patent license, your conveying the
    covered work in a country, or your recipient's use of the covered work
    in a country, would infringe one or more identifiable patents in that
    country that you have reason to believe are valid.

      If, pursuant to or in connection with a single transaction or
    arrangement, you convey, or propagate by procuring conveyance of, a
    covered work, and grant a patent license to some of the parties
    receiving the covered work authorizing them to use, propagate, modify
    or convey a specific copy of the covered work, then the patent license
    you grant is automatically extended to all recipients of the covered
    work and works based on it.

      A patent license is "discriminatory" if it does not include within
    the scope of its coverage, prohibits the exercise of, or is
    conditioned on the non-exercise of one or more of the rights that are
    specifically granted under this License.  You may not convey a covered
    work if you are a party to an arrangement with a third party that is
    in the business of distributing software, under which you make payment
    to the third party based on the extent of your activity of conveying
    the work, and under which the third party grants, to any of the
    parties who would receive the covered work from you, a discriminatory
    patent license (a) in connection with copies of the covered work
    conveyed by you (or copies made from those copies), or (b) primarily
    for and in connection with specific products or compilations that
    contain the covered work, unless you entered into that arrangement,
    or that patent license was granted, prior to 28 March 2007.

      Nothing in this License shall be construed as excluding or limiting
    any implied license or other defenses to infringement that may
    otherwise be available to you under applicable patent law.

      12. No Surrender of Others' Freedom.

      If conditions are imposed on you (whether by court order, agreement or
    otherwise) that contradict the conditions of this License, they do not
    excuse you from the conditions of this License.  If you cannot convey a
    covered work so as to satisfy simultaneously your obligations under this
    License and any other pertinent obligations, then as a consequence you may
    not convey it at all.  For example, if you agree to terms that obligate you
    to collect a royalty for further conveying from those to whom you convey
    the Program, the only way you could satisfy both those terms and this
    License would be to refrain entirely from conveying the Program.

      13. Use with the GNU Affero General Public License.

      Notwithstanding any other provision of this License, you have
    permission to link or combine any covered work with a work licensed
    under version 3 of the GNU Affero General Public License into a single
    combined work, and to convey the resulting work.  The terms of this
    License will continue to apply to the part which is the covered work,
    but the special requirements of the GNU Affero General Public License,
    section 13, concerning interaction through a network will apply to the
    combination as such.

      14. Revised Versions of this License.

      The Free Software Foundation may publish revised and/or new versions of
    the GNU General Public License from time to time.  Such new versions will
    be similar in spirit to the present version, but may differ in detail to
    address new problems or concerns.

      Each version is given a distinguishing version number.  If the
    Program specifies that a certain numbered version of the GNU General
    Public License "or any later version" applies to it, you have the
    option of following the terms and conditions either of that numbered
    version or of any later version published by the Free Software
    Foundation.  If the Program does not specify a version number of the
    GNU General Public License, you may choose any version ever published
    by the Free Software Foundation.

      If the Program specifies that a proxy can decide which future
    versions of the GNU General Public License can be used, that proxy's
    public statement of acceptance of a version permanently authorizes you
    to choose that version for the Program.

      Later license versions may give you additional or different
    permissions.  However, no additional obligations are imposed on any
    author or copyright holder as a result of your choosing to follow a
    later version.

      15. Disclaimer of Warranty.

      THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY
    APPLICABLE LAW.  EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT
    HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM "AS IS" WITHOUT WARRANTY
    OF ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO,
    THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
    PURPOSE.  THE ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM
    IS WITH YOU.  SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF
    ALL NECESSARY SERVICING, REPAIR OR CORRECTION.

      16. Limitation of Liability.

      IN NO EVENT UNLESS REQUIRED BY APPLICABLE LAW OR AGREED TO IN WRITING
    WILL ANY COPYRIGHT HOLDER, OR ANY OTHER PARTY WHO MODIFIES AND/OR CONVEYS
    THE PROGRAM AS PERMITTED ABOVE, BE LIABLE TO YOU FOR DAMAGES, INCLUDING ANY
    GENERAL, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES ARISING OUT OF THE
    USE OR INABILITY TO USE THE PROGRAM (INCLUDING BUT NOT LIMITED TO LOSS OF
    DATA OR DATA BEING RENDERED INACCURATE OR LOSSES SUSTAINED BY YOU OR THIRD
    PARTIES OR A FAILURE OF THE PROGRAM TO OPERATE WITH ANY OTHER PROGRAMS),
    EVEN IF SUCH HOLDER OR OTHER PARTY HAS BEEN ADVISED OF THE POSSIBILITY OF
    SUCH DAMAGES.

      17. Interpretation of Sections 15 and 16.

      If the disclaimer of warranty and limitation of liability provided
    above cannot be given local legal effect according to their terms,
    reviewing courts shall apply local law that most closely approximates
    an absolute waiver of all civil liability in connection with the
    Program, unless a warranty or assumption of liability accompanies a
    copy of the Program in return for a fee.

                         END OF TERMS AND CONDITIONS

                How to Apply These Terms to Your New Programs

      If you develop a new program, and you want it to be of the greatest
    possible use to the public, the best way to achieve this is to make it
    free software which everyone can redistribute and change under these terms.

      To do so, attach the following notices to the program.  It is safest
    to attach them to the start of each source file to most effectively
    state the exclusion of warranty; and each file should have at least
    the "copyright" line and a pointer to where the full notice is found.

        <one line to give the program's name and a brief idea of what it does.>
        Copyright (C) <year>  <name of author>

        This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 3 of the License, or
        (at your option) any later version.

        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
        GNU General Public License for more details.

        You should have received a copy of the GNU General Public License
        along with this program.  If not, see <https://www.gnu.org/licenses/>.

    Also add information on how to contact you by electronic and paper mail.

      If the program does terminal interaction, make it output a short
    notice like this when it starts in an interactive mode:

        <program>  Copyright (C) <year>  <name of author>
        This program comes with ABSOLUTELY NO WARRANTY; for details type `show w'.
        This is free software, and you are welcome to redistribute it
        under certain conditions; type `show c' for details.

    The hypothetical commands `show w' and `show c' should show the appropriate
    parts of the General Public License.  Of course, your program's commands
    might be different; for a GUI interface, you would use an "about box".

      You should also get your employer (if you work as a programmer) or school,
    if any, to sign a "copyright disclaimer" for the program, if necessary.
    For more information on this, and how to apply and follow the GNU GPL, see
    <https://www.gnu.org/licenses/>.

      The GNU General Public License does not permit incorporating your program
    into proprietary programs.  If your program is a subroutine library, you
    may consider it more useful to permit linking proprietary applications with
    the library.  If this is what you want to do, use the GNU Lesser General
    Public License instead of this License.  But first, please read
    <https://www.gnu.org/licenses/why-not-lgpl.html>
</p>
</details>




## Resources

* [ISO 8583 Wiki page](https://en.wikipedia.org/wiki/ISO_8583)
* [Payment service provider Wiki page](https://en.wikipedia.org/wiki/Payment_service_provider)
* [GNU licence page](https://www.gnu.org/licenses/)
* [Free software Wiki page](https://en.wikipedia.org/wiki/Free_software)
* [Qt documentation](https://doc.qt.io/)
* [Pydantic documentation](https://docs.pydantic.dev/latest/)


## Support

The project was designed and developed concerning the everyday needs of banking systems support engineers. 
It helped to save thousands of working hours and meet hundreds of deadlines. The basic monetization concept is that 
SIGNAL is free, always, and for everyone, not depending on usage. All the licensing and copyright targeting firstly 
to protect usage for free 

However, the project needs your support. If you want to support the project you can spend your time, working on it or 
make a voluntary donation directly to the author. ⚠️ Any donation can be voluntary only

The project needs help

* Code review, architecture development, advice
* Documentation development and translate
* Feedback, ideas
* Testing, especially auto-tests, unit-tests
* Financial support to BTC wallet

<details>
 <summary>️❤️Support the project</summary>
 <p align="left">
  <img src="https://i.imgur.com/Ms5iKQl.png" alt="BTC wallet" width="200"/>

```
bc1qs2jaqpnse9qgzz9y9wyns50km0f5x4wxe8cggs
```
</p>
</details>


## Author

Designed and developed by **Fedor Ivanov**   

In case of any question feel free to [contract author](mailto:fedornivanov@gmail.com?subject=SIGNAL%27s%20user%20request&body=Dear%20Fedor%2C%0A%0A%0A%3E%20Put%20your%20request%20here%20%3C%20%0A%0A%0A%0AMy%20SIGNAL%20version%20is%20v0.18%20%7C%20Released%20in%20May%202024%0A) directly
