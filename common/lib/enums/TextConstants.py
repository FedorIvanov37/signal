from enum import StrEnum
from common.lib.enums.ReleaseDefinition import ReleaseDefinition
from common.lib.enums.LicenseAgreement import LicenseAgreement


class TextConstants(StrEnum):
    SYSTEM_NAME = "SIGNAL"

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
                       "Postman collection, which covers basic needs.<br><br>Refer to the <a href=\"url.com\">User "
                       "Reference Guide</a> for details")

    USER_REFERENCE_GUIDE = '<a href=\"url.com\">User Reference Guide</a>'
