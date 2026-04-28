from pydantic import BaseModel, field_validator
from common.core.data_models.Countries import Countries
from common.core.data_models.Currencies import Currencies
from common.core.data_models.MerchCategories import MerchantCategoryCodes


class Dictionaries(BaseModel):
    currencies: Currencies | None = Currencies()
    countries: Countries | None = Countries()
    merch_cat_codes: MerchantCategoryCodes | None = MerchantCategoryCodes()

    @field_validator("merch_cat_codes", mode="before")
    @classmethod
    def substitute_none_mcc(cls, val):
        if val is None:
            return MerchantCategoryCodes()

        return val

    @field_validator("currencies", mode="before")
    @classmethod
    def substitute_none_currencies(cls, val):
        if val is None:
            return Currencies()

        return val

    @field_validator("countries", mode="before")
    @classmethod
    def substitute_none_countries(cls, val):
        if val is None:
            return Countries()

        return val
