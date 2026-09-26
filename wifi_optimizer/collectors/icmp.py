"""IPv4 ICMP with an explicit source address via Windows IcmpSendEcho2Ex."""
import ctypes as c
import ipaddress
import os
import time


def send_probes(target: str, source_ip: str, count: int, timeout_ms: int) -> list[dict]:
    if os.name != "nt":
        raise OSError("Windows ICMP API required")
    source = int.from_bytes(ipaddress.IPv4Address(source_ip).packed, "little")
    destination = int.from_bytes(ipaddress.IPv4Address(target).packed, "little")
    api = c.WinDLL("iphlpapi.dll", use_last_error=True)
    ptr, u32 = c.c_void_p, c.c_uint32
    api.IcmpCreateFile.argtypes = []
    api.IcmpCreateFile.restype = ptr
    api.IcmpCloseHandle.argtypes = [ptr]
    api.IcmpCloseHandle.restype = c.c_int
    api.IcmpSendEcho2Ex.argtypes = [ptr, ptr, ptr, ptr, u32, u32, ptr,
                                   c.c_uint16, ptr, ptr, u32, u32]
    api.IcmpSendEcho2Ex.restype = u32
    handle = api.IcmpCreateFile()
    if handle in (None, c.c_void_p(-1).value):
        raise OSError(c.get_last_error(), "IcmpCreateFile failed")
    samples = []
    request = c.create_string_buffer(b"wifi-quality-probe")
    try:
        for number in range(count):
            reply = c.create_string_buffer(4096)
            replies = api.IcmpSendEcho2Ex(
                handle, None, None, None, source, destination, request,
                len(request.raw) - 1, None, reply, len(reply), timeout_ms,
            )
            if replies:
                # ICMP_ECHO_REPLY begins with three DWORDs on both Windows ABIs:
                # Address, Status, RoundTripTime. Pointer-dependent tail is unused.
                header = c.cast(reply, c.POINTER(u32))
                status, rtt = header[1], header[2]
                samples.append({"status": "Success" if status == 0 else f"icmp_{status}",
                                "rtt_ms": rtt if status == 0 else None})
            else:
                error = c.get_last_error()
                samples.append({"status": "TimedOut" if error == 11010 else "send_error",
                                "rtt_ms": None, "error_code": error})
            if number < count - 1:
                time.sleep(0.25)
    finally:
        api.IcmpCloseHandle(handle)
    return samples
