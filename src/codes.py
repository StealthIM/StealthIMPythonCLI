ERR_CODES = {
    800: "Success",

    900: "Server Internal Error",
    901: "Server Internal Error",
    902: "Server Internal Error",
    903: "Server Internal Error",
    904: "Server Busy",
    905: "Too Big Request",
    906: "Server Internal Error",

    1000: "Server Internal Error",
    1001: "Empty UID",
    1002: "Empty Group ID",
    1003: "Empty Content",
    1004: "Unknown Message Type",
    1005: "Empty Message ID",
    1006: "Too Long Content",
    1007: "Message Not Found",
    1008: "Permission Denied",

    1100: "Server Internal Error",
    1101: "File Not Found",
    1102: "File Metadata Empty",
    1103: "File Metadata Error",
    1104: "File Hash Error",
    1106: "Server Storage Error",
    1107: "File Hash Error",
    1108: "Server Internal Error",
    1109: "Repeated File",

    1200: "Server Internal Error",
    1201: "User Not Found",
    1202: "User Already Exists",
    1203: "Wrong Password",
    1204: "Permission Denied",
    1205: "Invalid Arguments",

    1300: "Server Internal Error",
    1301: "Session Not Found",

    1400: "Server Internal Error",
    1401: "Server Internal Error",
    1402: "Group or User Not Found",
    1403: "Permission Denied",
    1404: "Already in Group",
    1405: "Password Incorrect",
    1406: "Server Internal Error",
    1407: "Server Internal Error",

    1500: "Server Internal Error",
    1501: "Bad Request",
    1502: "Authentication Failed",
}

def get_msg(code: int) -> str:
    return ERR_CODES.get(code, "Unknown Error")

SUCCESS = 800

MESSAGE_CONTENT_TOO_LONG = 1006
MESSAGE_MESSAGE_NOT_FOUND = 1007
MESSAGE_PERMISSION_DENIED = 1008

FILE_FILE_NOT_FOUND = 1101
FILE_METADATA_ERROR = 1103
FILE_HASH_ERROR = 1104
FILE_HASH_NOT_MATCH = 1107
FILE_REPEATED_FILE = 1109

USER_NOT_FOUND = 1201
USER_ALREADY_EXISTS = 1202
USER_WRONG_PASSWORD = 1203
USER_PERMISSION_DENIED = 1204

GROUP_USER_NOT_FOUND = 1402
GROUP_USER_PERMISSION_DENIED = 1403
GROUP_USER_ALREADY_IN_GROUP = 1404
GROUP_USER_PASSWORD_INCORRECT = 1405
