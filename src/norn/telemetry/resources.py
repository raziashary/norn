"""Observed per-process resources; unimplemented platforms report unavailable, never zero."""

import ctypes
import os
from typing import Any


def memory() -> dict[str, Any]:
    if os.name != "nt":
        return {
            "working_set_bytes": None,
            "peak_working_set_bytes": None,
            "scope": "UNMEASURED_PLATFORM",
        }
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("page_faults", wintypes.DWORD),
            *[
                (name, ctypes.c_size_t)
                for name in (
                    "peak",
                    "working",
                    "quota_peak_paged",
                    "quota_paged",
                    "quota_peak_nonpaged",
                    "quota_nonpaged",
                    "pagefile",
                    "peak_pagefile",
                )
            ],
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(Counters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    ):
        return {
            "working_set_bytes": None,
            "peak_working_set_bytes": None,
            "scope": "OS_QUERY_FAILED",
        }
    return {
        "working_set_bytes": counters.working,
        "peak_working_set_bytes": counters.peak,
        "pagefile_bytes": counters.pagefile,
        "scope": "CURRENT_PROCESS_WINDOWS_PSAPI",
    }
