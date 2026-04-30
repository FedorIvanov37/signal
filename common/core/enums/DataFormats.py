from enum import StrEnum


class DataFormats(StrEnum):
    INI = "INI"
    JSON = "JSON"
    DUMP = "DUMP"
    SPEC = "SPEC"
    OTHER = "OTHER"
    TERM = "SIGNAL"
    CONFIG = "CONFIG"


data_format_dict = dict[DataFormats, DataFormats]


print_data_formats: data_format_dict = {
    data_format.name: data_format.value for data_format in [
        DataFormats.JSON,
        DataFormats.INI,
        DataFormats.DUMP,
        DataFormats.SPEC,
        DataFormats.TERM,
        DataFormats.CONFIG,
    ]
}


input_files_formats: data_format_dict = {
    files_formats.name: files_formats.value for files_formats in [
        DataFormats.JSON,
        DataFormats.INI,
        DataFormats.DUMP,
    ]
}


output_files_formats: data_format_dict = {
    files_formats.name: files_formats.value for files_formats in [
        DataFormats.JSON,
        DataFormats.INI,
        DataFormats.DUMP,
    ]
}


PrintDataFormats = StrEnum("PrintDataFormats", print_data_formats)


InputFilesFormat = StrEnum("InputFilesFormat", input_files_formats)


OutputFilesFormat = StrEnum("OutputFilesFormat", output_files_formats)
