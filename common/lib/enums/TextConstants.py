from enum import StrEnum
from common.lib.enums.ReleaseDefinition import ReleaseDefinition
from common.lib.enums.LicenseAgreement import LicenseAgreement


class TextConstants(StrEnum):
    SYSTEM_NAME = "Signal"

    HELLO_MESSAGE = f"""
  ::::::::  :::::::::::  ::::::::   ::::    :::      :::      :::        
 :+:    :+:     :+:     :+:    :+:  :+:+:   :+:    :+: :+:    :+:        
 +:+            +:+     +:+         :+:+:+  +:+   +:+   +:+   +:+        
 +#++:++#++     +#+     :#:         +#+ +:+ +#+  +#++:++#++:  +#+        
        +#+     +#+     +#+   +#+#  +#+  +#+#+#  +#+     +#+  +#+        
 #+#    #+#     #+#     #+#    #+#  #+#   #+#+#  #+#     #+#  #+#        
  ########  ###########  ########   ###    ####  ###     ###  ########## 

  Simplified ISO generation algorithm {ReleaseDefinition.VERSION}"""

    LICENSE_AGREEMENT = LicenseAgreement.AGREEMENT

    CLI_DESCRIPTION = f"{SYSTEM_NAME} {ReleaseDefinition.VERSION}"

    API_EXPLANATION = ("Signal provides HTTP API for external integration. It also has a built-in "
                       "Postman collection, which covers basic needs.<br><br>Refer to the <a href=\"url.com\"> openapi "
                       "documentation</a> for details")

    USER_REFERENCE_GUIDE = '<a href=\"url.com\">User Reference Guide</a>'

    ECHO_TEST_RESPONSE = '''{
  "trans_id": "20260308_075419_9487802073",
  "message_type": "0810",
  "data_fields": {
    "7": "0308075419",
    "11": "414743",
    "38": "FJ1OEF",
    "39": "00",
    "70": "301"
  },
  "match_id": "20260308_075419_6998706576",
  "utrnno": null,
  "resp_time_seconds": 0.719
}'''

    OPENAPI_HELLO_MESSAGE = f'''```text {HELLO_MESSAGE}
```

## Purpose

The Signal API simplifies the sending of banking card e-commerce transactions to banking card processing systems using a 
useful program interface. It uses ISO-8583 E-pay protocol for transactions sending, instead of PSP 

The Signal API can be used during the Payment Systems certification test, for checking and setting up the system on the 
test environment, during the application development process, and so on

## Quick start

A minimal example of the API usage - send echo-test transaction request to the remote host 

```bash
$ curl -X POST %s
```

Run the example. In case of predefined transaction request Signal API returns the transaction response. We added jq 
command to get beautified JSON output

```bash
$ curl -X POST %s | jq  # We added jq command to get beautified JSON output

%s

$ 
```

## Resources 

| Resource                         | Link             |
|----------------------------------|------------------|
| General User Reference Guide     | [Open page](%s)  |
| The Latest Postman Collection    | [Download](%s)   |
| Signal API Live Log Tool         | [Open page](%s)  | 
'''
