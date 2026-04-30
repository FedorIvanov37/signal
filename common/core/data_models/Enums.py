from enum import Enum
from common.core.tools.EpaySpecification import EpaySpecification


spec: EpaySpecification = EpaySpecification()

generated_field = Enum("generated_field", spec.get_generated_fields_dict())
