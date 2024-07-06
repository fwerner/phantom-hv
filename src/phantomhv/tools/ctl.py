#!/usr/bin/env python3
"""
Low-level control and monitoring command-line tool for Phantom HV modules.
"""

import argparse
import sys
import time

from phantomhv import PhantomHVIO


def _parse_set_dac_arg(arg):
    dac, level = map(int, arg.split(","))
    assert 0 <= dac <= 3
    assert 0 <= level <= 4095
    return dac, level


def main():
    parser = argparse.ArgumentParser("phantomhv-ctl", description=__doc__)
    parser.add_argument("address", help="IP address or hostname of the master module")
    parser.add_argument(
        "--slot",
        type=int,
        default=0,
        choices=range(8),
        help="module slot to communicate with",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "monitor",
        help="continuously read and print slave states",
    )
    subparsers.add_parser(
        "monitor-adcs",
        help="continuously read and print slave ADC readings",
    )
    subparsers.add_parser(
        "monitor-interval",
        type=float,
        default=0.5,
        metavar="dt",
        help="set monitoring interval (default: 1 s)",
    )
    subparsers.add_parser(
        "set-dac",
        type=_parse_set_dac_arg,
        metavar="dac,level",
        help="set output level (0-4095) of DAC (0-3)",
    )
    subparsers.add_parser("boot", help="boot application slot")
    subparsers.add_parser("reset", help="reset into bootloader")
    flash_parser = subparsers.add_parser(
        "flash",
        help="flash binary firmware image into application slot",
    )
    flash_parser.add_argument(
        "-f",
        "--file",
        metavar="BIN_IMAGE",
        type=argparse.FileType("rb"),
        help="firmware image to write into flash",
    )
    subparsers.add_parser("unlock-hv", help="enable HV")
    subparsers.add_parser("lock-hv", help="disable HV")
    enable_hv_parser = subparsers.add_parser(
        "enable-hv",
        help="enable HV channel",
    )
    enable_hv_parser.add_argument(
        "channel", choices=range(3), type=int, metavar="N", help="channel to enable"
    )
    disable_hv_parser = subparsers.add_parser("disable-hv", help="disable HV channel")
    disable_hv_parser.add_argument(
        "channel", choices=range(3), type=int, metavar="N", help="channel to disable"
    )

    args = parser.parse_args()

    io = PhantomHVIO(args.address)
    io.ping()

    if args.boot:
        io.boot_app(args.slot)
    elif args.reset:
        io.reset(args.slot)
    elif args.flash:
        print(f"Flashing {args.address}...")
        state_before = io.read_slave_state(args.slot)
        io.flash_app(args.flash.read(), args.slot)
        state_after = io.read_slave_state(args.slot)
        if (
            state_after.spi_rx_errors != state_before.spi_rx_errors
            or state_after.spi_rx_overruns != state_before.spi_rx_overruns
        ):
            print("[ERROR] SPI communication error - please retry.")
            sys.exit(1)
    elif args.unlock_hv:
        cfg = io.read_slave_dynamic_cfg(args.slot)
        cfg.hv_enable |= 1 << 3
        io.write_slave_dynamic_cfg(args.slot, cfg)
    elif args.lock_hv:
        cfg = io.read_slave_dynamic_cfg(args.slot)
        cfg.hv_enable &= ~(1 << 3)
        io.write_slave_dynamic_cfg(args.slot, cfg)
    elif args.disable_hv is not None:
        cfg = io.read_slave_dynamic_cfg(args.slot)
        cfg.hv_enable &= ~(1 << args.disable_hv)
        io.write_slave_dynamic_cfg(args.slot, cfg)
    elif args.enable_hv is not None:
        cfg = io.read_slave_dynamic_cfg(args.slot)
        cfg.hv_enable |= 1 << args.enable_hv
        io.write_slave_dynamic_cfg(args.slot, cfg)
    elif args.set_dac:
        dac, level = args.set_dac
        cfg = io.read_slave_dynamic_cfg(args.slot)
        cfg.hv_dac[dac] = level
        io.write_slave_dynamic_cfg(args.slot, cfg)

    if args.monitor_adcs:
        try:
            t0 = time.time()
            while True:
                t_before = time.time()
                adcs = io.read_slave_state(args.slot).adc_states
                t_after = time.time()
                print(
                    f"{t_after / 2 + t_before / 2:.3f} "
                    + " ".join(f"{adc:5.0f}" for adc in adcs)
                )
                if args.monitor_interval > 0:
                    t0 += args.monitor_interval
                    dt = t0 - time.time()
                    if dt > 0:
                        time.sleep(dt)
        except KeyboardInterrupt:
            print()
            pass
    elif args.monitor:
        try:
            t0 = time.time()
            while True:
                print(io.read_slave_static_cfg(args.slot), end=" ")
                print(io.read_slave_dynamic_cfg(args.slot), end=" ")
                print(io.read_slave_state(args.slot), flush=True)

                t0 += args.monitor_interval
                dt = t0 - time.time()
                if dt > 0:
                    time.sleep(dt)
        except KeyboardInterrupt:
            print()
            pass
