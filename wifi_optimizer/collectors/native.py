"""Small read-only Native Wi-Fi binding for driver RSSI (no active scan)."""

import ctypes as c
import os
import uuid


def query_rssi(interface_guid: str) -> int:
    if os.name != "nt":
        raise OSError("Native Wi-Fi requires Windows")
    # Fixed-width Windows ABI types; GUID memory uses little-endian fields.
    guid = (c.c_ubyte * 16).from_buffer_copy(uuid.UUID(interface_guid).bytes_le)
    api = c.WinDLL("wlanapi.dll")
    dword = c.c_uint32
    pointer = c.c_void_p
    api.WlanOpenHandle.argtypes = [dword, pointer, c.POINTER(dword), c.POINTER(pointer)]
    api.WlanOpenHandle.restype = dword
    api.WlanQueryInterface.argtypes = [pointer, pointer, dword, pointer,
                                     c.POINTER(dword), c.POINTER(pointer), c.POINTER(dword)]
    api.WlanQueryInterface.restype = dword
    api.WlanFreeMemory.argtypes = [pointer]
    api.WlanFreeMemory.restype = None
    api.WlanCloseHandle.argtypes = [pointer, pointer]
    api.WlanCloseHandle.restype = dword
    handle, data = pointer(), pointer()
    version, size, opcode_type = dword(), dword(), dword()
    result = api.WlanOpenHandle(2, None, c.byref(version), c.byref(handle))
    if result:
        raise OSError(result, "WlanOpenHandle failed")
    try:
        result = api.WlanQueryInterface(handle, c.byref(guid), 0x10000102, None,
                                        c.byref(size), c.byref(data), c.byref(opcode_type))
        if result:
            raise OSError(result, "RSSI query failed")
        if not data.value or size.value < c.sizeof(c.c_int32):
            raise OSError("Invalid RSSI response")
        value = c.cast(data, c.POINTER(c.c_int32)).contents.value
        if not -127 <= value < 0:
            raise OSError("Driver RSSI is outside the supported range")
        return value
    finally:
        if data.value:
            api.WlanFreeMemory(data)
        api.WlanCloseHandle(handle, None)
