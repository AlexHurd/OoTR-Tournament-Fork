import io
import json
import logging
import os
import platform
import struct
import subprocess
import random

from Hints import buildGossipHints, buildBossRewardHints, buildGanonText
from Utils import local_path, default_output_path
from Items import ItemFactory, item_data
from Messages import *
from OcarinaSongs import Song, replace_songs, subsong

TunicColors = {
    "Kokiri Green": [0x1E, 0x69, 0x1B],
    "Goron Red": [0x64, 0x14, 0x00],
    "Zora Blue": [0x00, 0x3C, 0x64],
    "Black": [0x30, 0x30, 0x30],
    "White": [0xF0, 0xF0, 0xFF],
    "Purple": [0x95, 0x30, 0x80],
    "Yellow": [0xE0, 0xD8, 0x60],
    "Orange": [0xE0, 0x79, 0x40],
    "Pink": [0xFF, 0x90, 0xB3],
    "Gray": [0xA0, 0xA0, 0xB0],
    "Brown": [0x95, 0x59, 0x0A],
    "Gold": [0xD8, 0xB0, 0x60],
    "Silver": [0xD0, 0xF0, 0xFF],
    "Beige": [0xC0, 0xA0, 0xA0],
    "Teal": [0x30, 0xD0, 0xB0],
    "Royal Blue": [0x40, 0x00, 0x90],
    "Sonic Blue": [0x50, 0x90, 0xE0],
    "Blood Red": [0x30, 0x10, 0x10],
    "Blood Orange": [0xF0, 0x30, 0x30],
    "NES Green": [0x00, 0xD0, 0x00],
    "Dark Green": [0x00, 0x25, 0x18],
    "Only": [80, 140, 240],
}

NaviColors = {
    "White": [0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0xFF, 0x00],
    "Green": [0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0x00],
    "Light Blue": [0x96, 0x96, 0xFF, 0xFF, 0x96, 0x96, 0xFF, 0x00],
    "Yellow": [0xFF, 0xFF, 0x00, 0xFF, 0xC8, 0x9B, 0x00, 0x00],
    "Red": [0xFF, 0x00, 0x00, 0xFF, 0xFF, 0x00, 0x00, 0x00],
    "Magenta": [0xFF, 0x00, 0xFF, 0xFF, 0xC8, 0x00, 0x9B, 0x00],
    "Black": [0x00, 0x00, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x00],
    "Tatl": [0xFF, 0xFF, 0xFF, 0xFF, 0xC8, 0x98, 0x00, 0x00],
    "Tael": [0x49, 0x14, 0x6C, 0xFF, 0xFF, 0x00, 0x00, 0x00],
}

def get_tunic_colors():
    return list(TunicColors.keys())

def get_tunic_color_options():
    return ["Random Choice", "Completely Random"] + get_tunic_colors()

def get_navi_colors():
    return list(NaviColors.keys())

def get_navi_color_options():
    return ["Random Choice", "Completely Random"] + get_navi_colors()

class LocalRom(object):

    def __init__(self, settings, patch=True):
        file = settings.rom
        decomp_file = os.path.join(default_output_path(settings.output_dir), 'ZOOTDEC.z64')

        validCRC = []
        validCRC.append(bytearray([0xEC, 0x70, 0x11, 0xB7, 0x76, 0x16, 0xD7, 0x2B])) # Compressed
        validCRC.append(bytearray([0x70, 0xEC, 0xB7, 0x11, 0x16, 0x76, 0x2B, 0xD7])) # Byteswap compressed
        validCRC.append(bytearray([0x93, 0x52, 0x2E, 0x7B, 0xE5, 0x06, 0xD4, 0x27])) # Decompressed

        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        #os.chdir(output_path(os.path.dirname(os.path.realpath(__file__))))
        with open(file, 'rb') as stream:
            self.buffer = read_rom(stream)
        file_name = os.path.splitext(file)
        romCRC = self.buffer[0x10:0x18]
        if romCRC not in validCRC:
            raise RuntimeError('ROM is not a valid OoT 1.0 US ROM.')
        if len(self.buffer) < 33554432 or len(self.buffer) > 67108864 or file_name[1] not in ['.z64', '.n64']:
            raise RuntimeError('ROM is not a valid OoT 1.0 ROM.')
        if len(self.buffer) == 33554432:
            if platform.system() == 'Windows':
                subprocess.call(["Decompress\\Decompress.exe", file, decomp_file])
                with open(decomp_file, 'rb') as stream:
                    self.buffer = read_rom(stream)
            elif platform.system() == 'Linux':
                subprocess.call(["Decompress/Decompress", file])
                with open(("ZOOTDEC.z64"), 'rb') as stream:
                    self.buffer = read_rom(stream)
            elif platform.system() == 'Darwin':
                subprocess.call(["Decompress/Decompress.out", file])
                with open(("ZOOTDEC.z64"), 'rb') as stream:
                    self.buffer = read_rom(stream)
            else:
                raise RuntimeError('Unsupported operating system for decompression. Please supply an already decompressed ROM.')
        # extend to 64MB
        self.buffer.extend(bytearray([0x00] * (67108864 - len(self.buffer))))
            
    def read_byte(self, address):
        return self.buffer[address]

    def read_bytes(self, address, len):
        return self.buffer[address : address + len]

    def read_int16(self, address):
        return bytes_as_int16(self.read_bytes(address, 2))

    def read_int24(self, address):
        return bytes_as_int24(self.read_bytes(address, 3))

    def read_int32(self, address):
        return bytes_as_int32(self.read_bytes(address, 4))

    def write_byte(self, address, value):
        self.buffer[address] = value

    def write_bytes(self, startaddress, values):
        for i, value in enumerate(values):
            self.write_byte(startaddress + i, value)

    def write_int16(self, address, value):
        self.write_bytes(address, int16_as_bytes(value))

    def write_int24(self, address, value):
        self.write_bytes(address, int24_as_bytes(value))

    def write_int32(self, address, value):
        self.write_bytes(address, int32_as_bytes(value))

    def write_to_file(self, file):
        with open(file, 'wb') as outfile:
            outfile.write(self.buffer)

def read_rom(stream):
    "Reads rom into bytearray"
    buffer = bytearray(stream.read())
    return buffer


def int16_as_bytes(value):
    value = value & 0xFFFF
    return [(value >> 8) & 0xFF, value & 0xFF]

def int24_as_bytes(value):
    value = value & 0xFFFFFFFF
    return [(value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF]

def int32_as_bytes(value):
    value = value & 0xFFFFFFFF
    return [(value >> 24) & 0xFF, (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF]

def bytes_as_int16(values):
    return (values[0] << 8) | values[1]

def bytes_as_int24(values):
    return (values[0] << 16) | (values[1] << 8) | values[2]

def bytes_as_int32(values):
    return (values[0] << 24) | (values[1] << 16) | (values[2] << 8) | values[3]




def patch_rom(world, rom):
    with open(local_path('data/base2current.json'), 'r') as stream:
        patches = json.load(stream)
    for patch in patches:
        if isinstance(patch, dict):
            for baseaddress, values in patch.items():
                rom.write_bytes(int(baseaddress), values)

    # Can always return to youth
    rom.write_byte(0xCB6844, 0x35)
    rom.write_byte(0x253C0E2, 0x03) # Moves sheik from pedestal

    # Fix child shooting gallery reward to be static
    rom.write_bytes(0xD35EFC, [0x00, 0x00, 0x00, 0x00])

    # Fix target in woods reward to be static
    rom.write_bytes(0xE59CD4, [0x00, 0x00, 0x00, 0x00])

    # Fix GS rewards to be static
    rom.write_bytes(0xEA3934, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xEA3940 , [0x10, 0x00])

    # Fix horseback archery rewards to be static
    rom.write_byte(0xE12BA5, 0x00)
    rom.write_byte(0xE12ADD, 0x00)

    # Fix adult shooting gallery reward to be static
    rom.write_byte(0xD35F55, 0x00)

    # Fix deku theater rewards to be static
    rom.write_bytes(0xEC9A7C, [0x00, 0x00, 0x00, 0x00]) #Sticks
    rom.write_byte(0xEC9CD5, 0x00) #Nuts

    # Fix deku scrub who sells stick upgrade
    rom.write_bytes(0xDF8060, [0x00, 0x00, 0x00, 0x00])

    # Fix deku scrub who sells nut upgrade
    rom.write_bytes(0xDF80D4, [0x00, 0x00, 0x00, 0x00])

    # Fix rolling goron as child reward to be static
    rom.write_bytes(0xED2960, [0x00, 0x00, 0x00, 0x00])

    # Fix proximity text boxes (Navi) (Part 1)
    rom.write_bytes(0xDF8B84, [0x00, 0x00, 0x00, 0x00])

    # Fix final magic bean to cost 99
    rom.write_byte(0xE20A0F, 0x63)
    rom.write_bytes(0x94FCDD, [0x08, 0x39, 0x39])
    
    # Remove intro cutscene
    rom.write_bytes(0xB06BBA, [0x00, 0x00])

    # Remove locked door to Boss Key Chest in Fire Temple
    rom.write_byte(0x22D82B7, 0x3F)

    if world.bombchus_in_logic:
        # Change Bombchu Shop check to bombchus
        rom.write_bytes(0xC6CED8, [0x80, 0x8A, 0x00, 0x7C, 0x24, 0x0B, 0x00, 0x09, 0x11, 0x4B, 0x00, 0x05])
        # Change Bombchu Shop to never sell out
        rom.write_bytes(0xC019C0, [0x10, 0x00, 0x00, 0x30])

        # Change Bowling Alley check to bombchus (Part 1)
        rom.write_bytes(0x00E2D714, [0x81, 0xEF, 0xA6, 0x4C])
        rom.write_bytes(0x00E2D720, [0x24, 0x18, 0x00, 0x09, 0x11, 0xF8, 0x00, 0x06])

        # Change Bowling Alley check to bombchus (Part 2)
        rom.write_bytes(0x00E2D890,  [0x81, 0x6B, 0xA6, 0x4C, 0x24, 0x0C, 0x00, 0x09, 0x51, 0x6C, 0x00, 0x0A])
    else:
        # Change Bombchu Shop check to Bomb Bag
        rom.write_bytes(0xC6CEDA, [0x00, 0xA2])
        rom.write_byte(0xC6CEDF, 0x18)

        # Change Bowling Alley check to Bomb Bag (Part 1)
        rom.write_bytes(0x00E2D716, [0xA6, 0x72])
        rom.write_byte(0x00E2D723, 0x18)

        # Change Bowling Alley check to Bomb Bag (Part 2)
        rom.write_bytes(0x00E2D892, [0xA6, 0x72])
        rom.write_byte(0x00E2D897, 0x18)

    # Change Bazaar check to Bomb Bag (Child?)
    rom.write_bytes(0x00C0082A, [0x00, 0x18])
    rom.write_bytes(0x00C0082C, [0x00, 0x0E, 0X74, 0X02])
    rom.write_byte(0x00C00833, 0xA0)

    # Change Bazaar check to Bomb Bag (Adult?)
    rom.write_bytes(0x00DF7A8E, [0x00, 0x18])
    rom.write_bytes(0x00DF7A90, [0x00, 0x0E, 0X74, 0X02])
    rom.write_byte(0x00DF7A97, 0xA0)

    # Change Goron Shop check to Bomb Bag
    rom.write_bytes(0x00C6ED86, [0x00, 0xA2])
    rom.write_bytes(0x00C6ED8A, [0x00, 0x18])

    # Change graveyard graves to not allow grabbing on to the ledge
    rom.write_byte(0x0202039D, 0x20)
    rom.write_byte(0x0202043C, 0x24)

    # Fix Link the Goron to always work
    rom.write_bytes(0xED2FAC, [0x80, 0x6E, 0x0F, 0x18])
    rom.write_bytes(0xED2FEC, [0x24, 0x0A, 0x00, 0x00])
    rom.write_bytes(0xAE74D8, [0x24, 0x0E, 0x00, 0x00])

    # Fix King Zora Thawed to always work
    rom.write_bytes(0xE55C4C, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xE56290, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xE56298, [0x00, 0x00, 0x00, 0x00])

    # Fix Castle Courtyard to check for meeting Zelda, not Zelda fleeing, to block you
    rom.write_bytes(0xCD5E76, [0x0E, 0xDC])
    rom.write_bytes(0xCD5E12, [0x0E, 0xDC])

    # Cutscene for all medallions never triggers when leaving shadow or spirit temples(hopefully stops warp to colossus on shadow completion with boss reward shuffle)
    rom.write_byte(0xACA409, 0xAD)
    rom.write_byte(0xACA49D, 0xCE)
    
    # Speed Zelda's Letter scene
    rom.write_bytes(0x290E08E, [0x05, 0xF0])
    rom.write_byte(0xEFCBA7, 0x08)
    rom.write_byte(0xEFE7C7, 0x05)
    #rom.write_byte(0xEFEAF7, 0x08)
    #rom.write_byte(0xEFE7C7, 0x05)
    rom.write_bytes(0xEFE938, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xEFE948, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xEFE950, [0x00, 0x00, 0x00, 0x00])

    # Speed Zelda escaping from Hyrule Castle
    Block_code = [0x00, 0x00, 0x00, 0x01, 0x00, 0x21, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02]
    rom.write_bytes(0x1FC0CF8, Block_code)

    # Speed learning Zelda's Lullaby
    Block_code = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                  0x00, 0x00, 0x03, 0xE8, 0x00, 0x00, 0x00, 0x01, 0x00, 0x73, 0x00, 0x3B,
                  0x00, 0x3C, 0x00, 0x3C, 0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x0C,
                  0x00, 0x17, 0x00, 0x00, 0x00, 0x10, 0x00, 0x02, 0x08, 0x8B, 0xFF, 0xFF,
                  0x00, 0xD4, 0x00, 0x11, 0x00, 0x20, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x2E8E900, Block_code)

    # Speed learning Sun's Song
    rom.write_bytes(0x332A4A6, [0x00, 0x3C])
    Block_code = [0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x08, 0x00, 0x18, 0x00, 0x00,
                  0x00, 0x10, 0x00, 0x02, 0x08, 0x8B, 0xFF, 0xFF, 0x00, 0xD3, 0x00, 0x11,
                  0x00, 0x20, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x332A868, Block_code)

    # Speed learning Saria's Song
    rom.write_bytes(0x20B1736, [0x00, 0x3C])
    Block_code = [0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x15, 0x00, 0x00,
                  0x00, 0x10, 0x00, 0x02, 0x08, 0x8B, 0xFF, 0xFF, 0x00, 0xD1, 0x00, 0x11,
                  0x00, 0x20, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x20B1DA8, Block_code)
    rom.write_bytes(0x20B19C8, [0x00, 0x11, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00])
    Block_code = [0x00, 0x3E, 0x00, 0x11, 0x00, 0x20, 0x00, 0x00, 0x80, 0x00, 0x00, 0x00,
                  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0xD4, 0xFF, 0xFF, 0xF7, 0x31,
                  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0xD4]
    rom.write_bytes(0x20B19F8, Block_code)

    # Speed learning Epona's Song
    rom.write_bytes(0x29BEF68, [0x00, 0x5E, 0x00, 0x0A, 0x00, 0x0B, 0x00, 0x0B])
    Block_code = [0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x02, 0x00, 0xD2, 0x00, 0x00,
                  0x00, 0x09, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x0A,
                  0x00, 0x3C, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x29BECB0, Block_code)

    # Speed learning Song of Time
    Block_code = [0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x19, 0x00, 0x00,
                  0x00, 0x10, 0x00, 0x02, 0x08, 0x8B, 0xFF, 0xFF, 0x00, 0xD5, 0x00, 0x11,
                  0x00, 0x20, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x252FC80, Block_code)
    rom.write_bytes(0x252FBA0, [0x00, 0x35, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0x1FC3B84, [0xFF, 0xFF, 0xFF, 0xFF])

    # Speed learning Song of Storms
    Block_code = [0x00, 0x00, 0x00, 0x0A, 0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x02,
                  0x00, 0xD6, 0x00, 0x00, 0x00, 0x09, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF,
                  0xFF, 0xFF, 0x00, 0xBE, 0x00, 0xC8, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x3041084, Block_code)

    # Speed learning Minuet of Forest
    rom.write_bytes(0x20AFF86, [0x00, 0x3C])
    Block_code = [0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x0A, 0x00, 0x0F, 0x00, 0x00,
                  0x00, 0x10, 0x00, 0x02, 0x08, 0x8B, 0xFF, 0xFF, 0x00, 0x73, 0x00, 0x11,
                  0x00, 0x20, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x20B0800, Block_code)
    rom.write_bytes(0x20AFF90, [0x00, 0x11, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00])
    rom.write_bytes(0x20AFFC1, [0x00, 0x3E, 0x00, 0x11, 0x00, 0x20, 0x00, 0x00])
    rom.write_bytes(0x20B0492, [0x00, 0x21, 0x00, 0x22])
    rom.write_bytes(0x20B04CA, [0x00, 0x00, 0x00, 0x00])

    # Speed learning Bolero of Fire
    rom.write_bytes(0x224B5D6, [0x00, 0x3C])
    Block_code = [0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x0A, 0x00, 0x10, 0x00, 0x00,
                  0x00, 0x10, 0x00, 0x02, 0x08, 0x8B, 0xFF, 0xFF, 0x00, 0x74, 0x00, 0x11,
                  0x00, 0x20, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x224D7E8, Block_code)
    rom.write_bytes(0x224B5E0, [0x00, 0x11, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00])
    rom.write_bytes(0x224B611, [0x00, 0x3E, 0x00, 0x11, 0x00, 0x20, 0x00, 0x00])
    rom.write_bytes(0x224B7F8, [0x00, 0x00])
    rom.write_bytes(0x224B828, [0x00, 0x00])
    rom.write_bytes(0x224B858, [0x00, 0x00])
    rom.write_bytes(0x224B888, [0x00, 0x00])

    # Speed learning Serenade of Water
    rom.write_bytes(0x2BEB256, [0x00, 0x3C])
    Block_code = [0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x10, 0x00, 0x11, 0x00, 0x00,
                  0x00, 0x10, 0x00, 0x02, 0x08, 0x8B, 0xFF, 0xFF, 0x00, 0x75, 0x00, 0x11,
                  0x00, 0x20, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x2BEC880, Block_code)
    rom.write_bytes(0x2BEB260, [0x00, 0x11, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00])
    rom.write_bytes(0x2BEB290, [0x00, 0x3E, 0x00, 0x11, 0x00, 0x20, 0x00, 0x00])
    rom.write_bytes(0x2BEB538, [0x00, 0x00])
    rom.write_bytes(0x2BEB548, [0x80, 0x00])
    rom.write_bytes(0x2BEB554, [0x80, 0x00])
    rom.write_bytes(0x2BEC852, [0x00, 0x21, 0x00, 0x22])

    # Speed learning Nocturne of Shadow
    rom.write_bytes(0x1FFE460, [0x00, 0x2F, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])
    rom.write_bytes(0x1FFFDF6, [0x00, 0x3C])
    Block_code = [0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x0E, 0x00, 0x13, 0x00, 0x00,
                  0x00, 0x10, 0x00, 0x02, 0x08, 0x8B, 0xFF, 0xFF, 0x00, 0x77, 0x00, 0x11,
                  0x00, 0x20, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x2000FD8, Block_code)
    rom.write_bytes(0x2000130, [0x00, 0x32, 0x00, 0x3A, 0x00, 0x3B, 0x00, 0x3B])

    # Speed learning Requiem of Spirit
    rom.write_bytes(0x218AF16, [0x00, 0x3C])
    Block_code = [0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x08, 0x00, 0x12, 0x00, 0x00,
                  0x00, 0x10, 0x00, 0x02, 0x08, 0x8B, 0xFF, 0xFF, 0x00, 0x76, 0x00, 0x11,
                  0x00, 0x20, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x218C574, Block_code)
    rom.write_bytes(0x218B480, [0x00, 0x30, 0x00, 0x3A, 0x00, 0x3B, 0x00, 0x3B])
    Block_code = [0x00, 0x11, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x40, 0x00, 0x00, 0x00,
                  0xFF, 0xFF, 0xFA, 0xF9, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x00, 0x01,
                  0xFF, 0xFF, 0xFA, 0xF9, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x00, 0x01,
                  0x0F, 0x67, 0x14, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01]
    rom.write_bytes(0x218AF20, Block_code)
    rom.write_bytes(0x218AF50, [0x00, 0x3E, 0x00, 0x11, 0x00, 0x20, 0x00, 0x00])

    # Speed learning Prelude of Light
    rom.write_bytes(0x252FD26, [0x00, 0x3C])
    Block_code = [0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x0E, 0x00, 0x14, 0x00, 0x00,
                  0x00, 0x10, 0x00, 0x02, 0x08, 0x8B, 0xFF, 0xFF, 0x00, 0x78, 0x00, 0x11,
                  0x00, 0x20, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x2531320, Block_code)
    rom.write_byte(0x252FF1D, 0x00)
    rom.write_bytes(0x25313DA, [0x00, 0x21, 0x00, 0x22])

    # Speed scene after Deku Tree
    rom.write_bytes(0x2077E20, [0x00, 0x07, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])
    rom.write_bytes(0x2078A10, [0x00, 0x0E, 0x00, 0x1F, 0x00, 0x20, 0x00, 0x20])
    Block_code = [0x00, 0x80, 0x00, 0x00, 0x00, 0x1E, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 
                  0xFF, 0xFF, 0x00, 0x1E, 0x00, 0x28, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x2079570, Block_code)

    # Speed scene after Dodongo's Cavern
    rom.write_bytes(0x2221E88, [0x00, 0x0C, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0x2223308, [0x00, 0x81, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])

    # Speed scene after Jabu Jabu's Belly
    rom.write_bytes(0xCA3530, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0x2113340, [0x00, 0x0D, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0x2113C18, [0x00, 0x82, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])
    rom.write_bytes(0x21131D0, [0x00, 0x01, 0x00, 0x00, 0x00, 0x3C, 0x00, 0x3C])

    # Speed scene after Forest Temple
    rom.write_bytes(0xD4ED68, [0x00, 0x45, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0xD4ED78, [0x00, 0x3E, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])
    rom.write_bytes(0x207B9D4, [0xFF, 0xFF, 0xFF, 0xFF])

    # Speed scene after Fire Temple
    rom.write_bytes(0x2001848, [0x00, 0x1E, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])
    rom.write_bytes(0xD100B4, [0x00, 0x62, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0xD10134, [0x00, 0x3C, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])

    # Speed scene after Water Temple
    rom.write_bytes(0xD5A458, [0x00, 0x15, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0xD5A3A8, [0x00, 0x3D, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])
    rom.write_bytes(0x20D0D20, [0x00, 0x29, 0x00, 0xC7, 0x00, 0xC8, 0x00, 0xC8])

    # Speed scene after Shadow Temple
    rom.write_bytes(0xD13EC8, [0x00, 0x61, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0xD13E18, [0x00, 0x41, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])

    # Speed scene after Spirit Temple
    rom.write_bytes(0xD3A0A8, [0x00, 0x60, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0xD39FF0, [0x00, 0x3F, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])

    # Speed Nabooru defeat scene
    rom.write_bytes(0x2F5AF84, [0x00, 0x00, 0x00, 0x05])
    rom.write_bytes(0x2F5C7DA, [0x00, 0x01, 0x00, 0x02])
    rom.write_bytes(0x2F5C7A2, [0x00, 0x03, 0x00, 0x04])
    rom.write_byte(0x2F5B369, 0x09)
    rom.write_byte(0x2F5B491, 0x04)
    rom.write_byte(0x2F5B559, 0x04)
    rom.write_byte(0x2F5B621, 0x04)
    rom.write_byte(0x2F5B761, 0x07)

    # Speed scene with all medallions
    rom.write_bytes(0x2512680, [0x00, 0x74, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])

    # Speed collapse of Ganon's Tower
    rom.write_bytes(0x33FB328, [0x00, 0x76, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])

    # Speed Phantom Ganon defeat scene
    rom.write_bytes(0xC944D8, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xC94548, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xC94730, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xC945A8, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xC94594, [0x00, 0x00, 0x00, 0x00])

    # Speed Twinrova defeat scene
    rom.write_bytes(0xD678CC, [0x24, 0x01, 0x03, 0xA2, 0xA6, 0x01, 0x01, 0x42])
    rom.write_bytes(0xD67BA4, [0x10, 0x00])
    
    # Speed scenes during final battle
    # Ganondorf battle end
    rom.write_byte(0xD82047, 0x09)
    # Zelda descends
    rom.write_byte(0xD82AB3, 0x66)
    rom.write_byte(0xD82FAF, 0x65)
    rom.write_bytes(0xD82D2E, [0x04, 0x1F])
    rom.write_bytes(0xD83142, [0x00, 0x6B])
    rom.write_bytes(0xD82DD8, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xD82ED4, [0x00, 0x00, 0x00, 0x00])
    rom.write_byte(0xD82FDF, 0x33)
    # After tower collapse
    rom.write_byte(0xE82E0F, 0x04)
    # Ganon intro
    rom.write_bytes(0xE83D28, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xE83B5C, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xE84C80, [0x10, 0x00])
    
    # Speed completion of the trials in Ganon's Castle
    rom.write_bytes(0x31A8090, [0x00, 0x6B, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02]) #Forest
    rom.write_bytes(0x31A9E00, [0x00, 0x6E, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02]) #Fire
    rom.write_bytes(0x31A8B18, [0x00, 0x6C, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02]) #Water
    rom.write_bytes(0x31A9430, [0x00, 0x6D, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02]) #Shadow
    rom.write_bytes(0x31AB200, [0x00, 0x70, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02]) #Spirit
    rom.write_bytes(0x31AA830, [0x00, 0x6F, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02]) #Light

    # Speed obtaining Fairy Ocarina
    rom.write_bytes(0x2150CD0, [0x00, 0x00, 0x00, 0x20,	0x00, 0x00, 0x00, 0x30])
    Block_code = [0xFF, 0xFF, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF,
                  0xFF, 0xFF, 0x00, 0x3C, 0x00, 0x81, 0xFF, 0xFF]
    rom.write_bytes(0x2151240, Block_code)
    rom.write_bytes(0x2150E20, [0xFF, 0xFF, 0xFA, 0x4C])

    # Speed Zelda Light Arrow cutscene
    rom.write_bytes(0x2531B40, [0x00, 0x28, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])
    rom.write_bytes(0x2532FBC, [0x00, 0x75])
    rom.write_bytes(0x2532FEA, [0x00, 0x75, 0x00, 0x80])  
    rom.write_byte(0x2533115, 0x05)
    rom.write_bytes(0x2533141, [0x06, 0x00, 0x06, 0x00, 0x10])
    rom.write_bytes(0x2533171, [0x0F, 0x00, 0x11, 0x00, 0x40])
    rom.write_bytes(0x25331A1, [0x07, 0x00, 0x41, 0x00, 0x65])
    rom.write_bytes(0x2533642, [0x00, 0x50])
    rom.write_byte(0x253389D, 0x74)
    rom.write_bytes(0x25338A4, [0x00, 0x72, 0x00, 0x75, 0x00, 0x79])
    rom.write_bytes(0x25338BC, [0xFF, 0xFF])
    rom.write_bytes(0x25338C2, [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    rom.write_bytes(0x25339C2, [0x00, 0x75, 0x00, 0x76])
    rom.write_bytes(0x2533830, [0x00, 0x31, 0x00, 0x81, 0x00, 0x82, 0x00, 0x82])

    # Speed Bridge of Light cutscene
    rom.write_bytes(0x292D644, [0x00, 0x00, 0x00, 0xA0])
    rom.write_bytes(0x292D680, [0x00, 0x02, 0x00, 0x0A, 0x00, 0x6C, 0x00, 0x00])
    rom.write_bytes(0x292D6E8, [0x00, 0x27])
    rom.write_bytes(0x292D718, [0x00, 0x32])
    rom.write_bytes(0x292D810, [0x00, 0x02, 0x00, 0x3C])
    rom.write_bytes(0x292D924, [0xFF, 0xFF, 0x00, 0x14, 0x00, 0x96, 0xFF, 0xFF])

    # Remove remaining owls
    rom.write_bytes(0x1FE30CE, [0x01, 0x4B])
    rom.write_bytes(0x1FE30DE, [0x01, 0x4B])
    rom.write_bytes(0x1FE30EE, [0x01, 0x4B])
    rom.write_bytes(0x205909E, [0x00, 0x3F])
    rom.write_byte(0x2059094, 0x80)

    # Darunia won't dance
    rom.write_bytes(0x22769E4, [0xFF, 0xFF, 0xFF, 0xFF])

    # Zora moves quickly
    rom.write_bytes(0xE56924, [0x00, 0x00, 0x00, 0x00])

    # Speed Jabu Jabu swallowing Link
    rom.write_bytes(0xCA0784, [0x00, 0x18, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])

    # Ruto no longer points to Zora Sapphire
    rom.write_bytes(0xD03BAC, [0xFF, 0xFF, 0xFF, 0xFF])

    # Ruto never disappears from Jabu Jabu's Belly
    rom.write_byte(0xD01EA3, 0x00)

    # Speed up Epona race start
    rom.write_bytes(0x29BE984, [0x00, 0x00, 0x00, 0x02])
    rom.write_bytes(0x29BE9CA, [0x00, 0x01, 0x00, 0x02])
	
    # Speed start of Horseback Archery
    #rom.write_bytes(0x21B2064, [0x00, 0x00, 0x00, 0x02])
    #rom.write_bytes(0x21B20AA, [0x00, 0x01, 0x00, 0x02])

    # Speed up Epona escape
    rom.write_bytes(0x1FC8B36, [0x00, 0x2A])

    # Speed up draining the well
    rom.write_bytes(0xE0A010, [0x00, 0x2A, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])
    rom.write_bytes(0x2001110, [0x00, 0x2B, 0x00, 0xB7, 0x00, 0xB8, 0x00, 0xB8])

    # Speed up opening the royal tomb for both child and adult
    rom.write_bytes(0x2025026, [0x00, 0x01])
    rom.write_bytes(0x2023C86, [0x00, 0x01])
    rom.write_byte(0x2025159, 0x02)
    rom.write_byte(0x2023E19, 0x02)

    #Speed opening of Door of Time
    rom.write_bytes(0xE0A176, [0x00, 0x02])
    rom.write_bytes(0xE0A35A, [0x00, 0x01, 0x00, 0x02])

    # Poacher's Saw no longer messes up Deku Theater
    rom.write_bytes(0xAE72CC, [0x00, 0x00, 0x00, 0x00])

    # Learning Serenade tied to opening chest in room
    Block_code = [0x3C, 0x0F, 0x80, 0x1D, 0x81, 0xE8, 0xA1, 0xDB, 0x24, 0x19, 0x00, 0x04,
                  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x8C, 0xA2, 0x1C, 0x44,
                  0x00, 0x00, 0x00, 0x00]
    rom.write_bytes(0xC7BCF0, Block_code)

    # Dampe Chest spawn condition looks at chest flag instead of having obtained hookshot
    Block_code = [0x93, 0x18, 0xAE, 0x7E, 0x27, 0xA5, 0x00, 0x24, 0x33, 0x19, 0x00, 0x01,
                  0x00, 0x00, 0x00, 0x00]
    rom.write_bytes(0xDFEC40, Block_code)

    # Darunia sets an event flag and checks for it
    Block_code = [0x24, 0x19, 0x00, 0x40, 0x8F, 0x09, 0xB4, 0xA8, 0x01, 0x39, 0x40, 0x24,
                  0x01, 0x39, 0xC8, 0x25, 0xAF, 0x19, 0xB4, 0xA8, 0x24, 0x09, 0x00, 0x06]
    rom.write_bytes(0xCF1AB8, Block_code)

    # Change Prelude CS to check for medallion
    rom.write_bytes(0x00C805E6, [0x00, 0xA6])
    rom.write_bytes(0x00C805F2, [0x00, 0x01])

    # Change Nocturne CS to check for medallions
    rom.write_bytes(0x00ACCD8E, [0x00, 0xA6])
    rom.write_bytes(0x00ACCD92, [0x00, 0x01])
    rom.write_bytes(0x00ACCD9A, [0x00, 0x02])
    rom.write_bytes(0x00ACCDA2, [0x00, 0x04])

    # Change King Zora to move even if Zora Sapphire is in inventory
    rom.write_bytes(0x00E55BB0, [0x85, 0xCE, 0x8C, 0x3C])
    rom.write_bytes(0x00E55BB4, [0x84, 0x4F, 0x0E, 0xDA])

    # Remove extra Forest Temple medallions
    rom.write_bytes(0x00D4D37C, [0x00, 0x00, 0x00, 0x00])

    # Remove extra Fire Temple medallions
    rom.write_bytes(0x00AC9754, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0x00D0DB8C, [0x00, 0x00, 0x00, 0x00])

    # Remove extra Water Temple medallions
    rom.write_bytes(0x00D57F94, [0x00, 0x00, 0x00, 0x00])

    # Remove extra Spirit Temple medallions
    rom.write_bytes(0x00D370C4, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0x00D379C4, [0x00, 0x00, 0x00, 0x00])

    # Remove extra Shadow Temple medallions
    rom.write_bytes(0x00D116E0, [0x00, 0x00, 0x00, 0x00])

    # Change Mido, Saria, and Kokiri to check for Deku Tree complete flag
    # bitwise pointer for 0x80
    kokiriAddresses = [0xE52836, 0xE53A56, 0xE51D4E, 0xE51F3E, 0xE51D96, 0xE51E1E, 0xE51E7E, 0xE51EDE, 0xE51FC6, 0xE51F96, 0xE293B6, 0xE29B8E, 0xE62EDA, 0xE630D6, 0xE62642, 0xE633AA, 0xE6369E]
    for kokiri in kokiriAddresses:
        rom.write_bytes(kokiri, [0x8C, 0x0C])
    # Kokiri
    rom.write_bytes(0xE52838, [0x94, 0x48, 0x0E, 0xD4])    
    rom.write_bytes(0xE53A58, [0x94, 0x49, 0x0E, 0xD4])
    rom.write_bytes(0xE51D50, [0x94, 0x58, 0x0E, 0xD4])
    rom.write_bytes(0xE51F40, [0x94, 0x4B, 0x0E, 0xD4])
    rom.write_bytes(0xE51D98, [0x94, 0x4B, 0x0E, 0xD4])
    rom.write_bytes(0xE51E20, [0x94, 0x4A, 0x0E, 0xD4])
    rom.write_bytes(0xE51E80, [0x94, 0x59, 0x0E, 0xD4])
    rom.write_bytes(0xE51EE0, [0x94, 0x4E, 0x0E, 0xD4])
    rom.write_bytes(0xE51FC8, [0x94, 0x49, 0x0E, 0xD4])
    rom.write_bytes(0xE51F98, [0x94, 0x58, 0x0E, 0xD4])
    # Saria
    rom.write_bytes(0xE293B8, [0x94, 0x78, 0x0E, 0xD4])
    rom.write_bytes(0xE29B90, [0x94, 0x68, 0x0E, 0xD4])
    # Mido
    rom.write_bytes(0xE62EDC, [0x94, 0x6F, 0x0E, 0xD4])
    rom.write_bytes(0xE630D8, [0x94, 0x4F, 0x0E, 0xD4])
    rom.write_bytes(0xE62644, [0x94, 0x6F, 0x0E, 0xD4])
    rom.write_bytes(0xE633AC, [0x94, 0x68, 0x0E, 0xD4])
    rom.write_bytes(0xE636A0, [0x94, 0x48, 0x0E, 0xD4])

    # Change adult Kokiri Forest to check for Forest Temple complete flag
    rom.write_bytes(0xE5369E, [0xB4, 0xAC])
    rom.write_bytes(0xD5A83C, [0x80, 0x49, 0x0E, 0xDC])

    # Change adult Goron City to check for Fire Temple complete flag
    rom.write_bytes(0xED59DC, [0x80, 0xC9, 0x0E, 0xDC])

    # Change Pokey to check DT complete flag
    rom.write_bytes(0xE5400A, [0x8C, 0x4C])
    rom.write_bytes(0xE5400E, [0xB4, 0xA4])
    if world.open_forest:
        rom.write_bytes(0xE5401C, [0x14, 0x0B])

    # Fix Shadow Temple to check for different rewards for scene
    rom.write_bytes(0xCA3F32, [0x00, 0x00, 0x25, 0x4A, 0x00, 0x10])

    # Fix Spirit Temple to check for different rewards for scene
    rom.write_bytes(0xCA3EA2, [0x00, 0x00, 0x25, 0x4A, 0x00, 0x08])

    # Fire Arrows now in a chest, always spawn
    rom.write_bytes(0xE9E202, [0x00, 0x0A])
    rom.write_bytes(0xE9E1F2, [0x5B, 0x08])
    rom.write_bytes(0xE9E1D8, [0x00, 0x00, 0x00, 0x00])

    # Fix Biggoron to check a different flag.
    rom.write_byte(0xED329B, 0x72)
    rom.write_byte(0xED43E7, 0x72)
    rom.write_bytes(0xED3370, [0x3C, 0x0D, 0x80, 0x12])
    rom.write_bytes(0xED3378, [0x91, 0xB8, 0xA6, 0x42, 0xA1, 0xA8, 0xA6, 0x42])
    rom.write_bytes(0xED6574, [0x00, 0x00, 0x00, 0x00])

    # Remove the check on the number of days that passed for claim check.
    rom.write_bytes(0xED4470, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xED4498, [0x00, 0x00, 0x00, 0x00])

    # Fixed reward order for Bombchu Bowling
    rom.write_bytes(0xE2E698, [0x80, 0xAA, 0xE2, 0x64])
    rom.write_bytes(0xE2E6A0, [0x80, 0xAA, 0xE2, 0x4C])
    rom.write_bytes(0xE2D440, [0x24, 0x19, 0x00, 0x00])

    # Make fishing less obnoxious
    Block_code = [0x3C, 0x0A, 0x80, 0x12, 0x8D, 0x4A, 0xA5, 0xD4, 0x14, 0x0A, 0x00, 0x06,
                  0x31, 0x78, 0x00, 0x01, 0x14, 0x18, 0x00, 0x02, 0x3c, 0x18, 0x42, 0x30,
                  0x3C, 0x18, 0x42, 0x50, 0x03, 0xe0, 0x00, 0x08, 0x00, 0x00, 0x00, 0x00,
                  0x14, 0x18, 0x00, 0x02, 0x3C, 0x18, 0x42, 0x10, 0x3C, 0x18, 0x42, 0x38,
                  0x03, 0xE0, 0x00, 0x08]
    rom.write_bytes(0x3480C00, Block_code)
    rom.write_bytes(0xDBF434, [0x44, 0x98, 0x90, 0x00, 0xE6, 0x52, 0x01, 0x9C])
    rom.write_bytes(0xDBF484, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xDBF4A8, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xDCBEAA, [0x42, 0x48]) #set adult fish size requirement
    rom.write_bytes(0xDCBF26, [0x42, 0x48]) #set adult fish size requirement
    rom.write_bytes(0xDCBF32, [0x42, 0x30]) #set child fish size requirement
    rom.write_bytes(0xDCBF9E, [0x42, 0x30]) #set child fish size requirement

    # Dampe always digs something up and first dig is always the Piece of Heart
    rom.write_bytes(0xCC3FA8, [0xA2, 0x01, 0x01, 0xF8])
    rom.write_bytes(0xCC4024, [0x00, 0x00, 0x00, 0x00])
    
    # Allow owl to always carry the kid down Death Mountain
    rom.write_bytes(0xE304F0, [0x24, 0x0E, 0x00, 0x01])

    # Forbid Sun's Song from a bunch of cutscenes
    Suns_scenes = [0x2016FC9, 0x2017219, 0x20173D9, 0x20174C9, 0x2017679, 0x20C1539, 0x20C15D9, 0x21A0719, 0x21A07F9, 0x2E90129, 0x2E901B9, 0x2E90249, 0x225E829, 0x225E939, 0x306D009]
    for address in Suns_scenes:
        rom.write_byte(address,0x01)

    # Remove forcible text triggers
    Wonder_text = [0x27C00C6, 0x27C00D6, 0x27C00E6, 0x27C00F6, 0x27C0106, 0x27C0116, 0x27C0126, 0x27C0136]
    for address in Wonder_text:
        rom.write_byte(address, 0x02)
    rom.write_byte(0x27CE08A, 0x09)
    rom.write_byte(0x27CE09A, 0x0F)
    Wonder_text = [0x288707A, 0x288708A, 0x288709A, 0x289707A, 0x28C713E, 0x28D91C6]
    for address in Wonder_text:
        rom.write_byte(address, 0x0C)
    Wonder_text = [0x28A60FE, 0x28AE08E, 0x28B917E, 0x28BF172, 0x28BF182, 0x28BF192]
    for address in Wonder_text:
        rom.write_byte(address, 0x0D)
    rom.write_byte(0x28A114E, 0x0E)
    rom.write_byte(0x28A610E, 0x0E)
    Wonder_text = [0x9367F6, 0x93673D, 0x93679D]
    for address in Wonder_text:
        rom.write_byte(address, 0x08)
    Wonder_text = [0x289707B, 0x28AE08F, 0x28C713F]
    for address in Wonder_text:
        rom.write_byte(address, 0xAF)
    rom.write_byte(0x28A114F, 0x6F)
    rom.write_byte(0x28B917F, 0x6F)
    rom.write_byte(0x28A60FF, 0xEF)
    rom.write_byte(0x28D91C7, 0xEF)
    Wonder_text = [0x28A610F, 0x28BF173, 0x28BF183, 0x28BF193]
    for address in Wonder_text:
        rom.write_byte(address, 0x2F)
    Wonder_text = [0x27CE08B, 0x27C00C7, 0x27C00D7, 0x27C0117, 0x27C0127]
    for address in Wonder_text:
        rom.write_byte(address, 0x3D)
    rom.write_byte(0x27C00E7, 0x7D)
    rom.write_byte(0x27C00F7, 0x7D)
    rom.write_byte(0x27C0107, 0xBD)
    rom.write_byte(0x27C0137, 0xBD)
    Wonder_text = [0x27C00BC, 0x27C00CC, 0x27C00DC, 0x27C00EC, 0x27C00FC, 0x27C010C, 0x27C011C, 0x27C012C, 0x27CE080, 0x27CE090, 0x2887070, 0x2887080, 0x2887090, 0x2897070, 0x28C7134, 0x28D91BC, 0x28A60F4, 0x28AE084, 0x28B9174, 0x28BF168, 0x28BF178, 0x28BF188, 0x28A1144, 0x28A6104]
    for address in Wonder_text:
        rom.write_byte(address, 0xFE)

    # Speed dig text for Dampe
    rom.write_bytes(0x9532F8, [0x08, 0x08, 0x08, 0x59])
    
    # Make item descriptions into a single box
    Short_item_descriptions = [0x92EC84, 0x92F9E3, 0x92F2B4, 0x92F37A, 0x92F513, 0x92F5C6, 0x92E93B, 0x92EA12]
    for address in Short_item_descriptions:
        rom.write_byte(address,0x02)

    # Fix text for Pocket Cucco.
    rom.write_byte(0xBEEF45, 0x0B)
    rom.write_byte(0x92D41A, 0x2E)
    Block_code = [0x59, 0x6f, 0x75, 0x20, 0x67, 0x6f, 0x74, 0x20, 0x61, 0x20, 0x05, 0x41,
                  0x50, 0x6f, 0x63, 0x6b, 0x65, 0x74, 0x20, 0x43, 0x75, 0x63, 0x63, 0x6f,
                  0x2c, 0x20, 0x05, 0x40, 0x6f, 0x6e, 0x65, 0x01, 0x6f, 0x66, 0x20, 0x41,
                  0x6e, 0x6a, 0x75, 0x27, 0x73, 0x20, 0x70, 0x72, 0x69, 0x7a, 0x65, 0x64,
                  0x20, 0x68, 0x65, 0x6e, 0x73, 0x21, 0x20, 0x49, 0x74, 0x20, 0x66, 0x69,
                  0x74, 0x73, 0x20, 0x01, 0x69, 0x6e, 0x20, 0x79, 0x6f, 0x75, 0x72, 0x20,
                  0x70, 0x6f, 0x63, 0x6b, 0x65, 0x74, 0x2e, 0x02]
    rom.write_bytes(0x92D41C, Block_code)

    # DMA in extra code
    Block_code = [0xAF, 0xBF, 0x00, 0x1C, 0xAF, 0xA4, 0x01, 0x40, 0x3C, 0x05, 0x03, 0x48,
                  0x3C, 0x04, 0x80, 0x40, 0x0C, 0x00, 0x03, 0x7C, 0x24, 0x06, 0x50, 0x00,
                  0x0C, 0x10, 0x02, 0x00]
    rom.write_bytes(0xB17BB4, Block_code)
    Block_code = [0x3C, 0x02, 0x80, 0x12, 0x24, 0x42, 0xD2, 0xA0, 0x24, 0x0E, 0x01, 0x40,
                  0xAC, 0x2E, 0xE5, 0x00, 0x03, 0xE0, 0x00, 0x08, 0x00, 0x00, 0x00, 0x00]
    rom.write_bytes(0x3480800, Block_code)
    rom.write_bytes(0xD270, [0x03, 0x48, 0x00, 0x00, 0x03, 0x48, 0x50, 0x00, 0x03, 0x48, 0x00, 0x00])

    # Fix checksum (Thanks Nintendo)
    Block_code = [0x93, 0x5E, 0x8E, 0x5B, 0xD0, 0x9C, 0x5A, 0x58]
    rom.write_bytes(0x10, Block_code)

    # Set hooks for various code
    rom.write_bytes(0xDBF428, [0x0C, 0x10, 0x03, 0x00]) #Set Fishing Hook


    # will be populated with data to be written to initial save
    # see initial_save.asm and config.asm for more details on specifics
    # or just use the following functions to add an entry to the table
    initial_save_table = []

    # will set the bits of value to the offset in the save (or'ing them with what is already there)
    def write_bits_to_save(offset, value, filter=None):
        nonlocal initial_save_table

        if filter and not filter(value):
            return

        initial_save_table += [(offset & 0xFF00) >> 8, offset & 0xFF, 0x00, value]
        


    # will overwrite the byte at offset with the given value
    def write_byte_to_save(offset, value, filter=None):
        nonlocal initial_save_table

        if filter and not filter(value):
            return

        initial_save_table += [(offset & 0xFF00) >> 8, offset & 0xFF, 0x01, value]

    # will overwrite the byte at offset with the given value
    def write_bytes_to_save(offset, bytes, filter=None):
        for i, value in enumerate(bytes):
            write_byte_to_save(offset + i, value, filter)

    # will overwrite the byte at offset with the given value
    def write_save_table(rom):
        nonlocal initial_save_table

        table_len = len(initial_save_table)
        if table_len > 0x400:
            raise Exception("The Initial Save Table has exceeded it's maximum capacity: 0x%03X/0x400" % table_len)
        rom.write_bytes(0x3481800, initial_save_table)


    # Initial Save Data
    write_bits_to_save(0x003F, 0x02) # Some Biggoron's Sword flag?

    write_bits_to_save(0x00D4 + 0x00 * 0x1C + 0x04 + 0x0, 0x80) # Deku tree switch flag (navi text?)
    write_bits_to_save(0x00D4 + 0x00 * 0x1C + 0x04 + 0x1, 0x02) # Deku tree switch flag (navi text?)
    write_bits_to_save(0x00D4 + 0x00 * 0x1C + 0x04 + 0x2, 0x80) # Deku tree switch flag (navi text?)
    write_bits_to_save(0x00D4 + 0x00 * 0x1C + 0x04 + 0x2, 0x04) # Deku tree switch flag (navi text?)
    write_bits_to_save(0x00D4 + 0x01 * 0x1C + 0x04 + 0x2, 0x40) # Dodongo's Cavern switch flag (navi text?)
    write_bits_to_save(0x00D4 + 0x01 * 0x1C + 0x04 + 0x2, 0x08) # Dodongo's Cavern switch flag (navi text?)
    write_bits_to_save(0x00D4 + 0x01 * 0x1C + 0x04 + 0x2, 0x01) # Dodongo's Cavern switch flag (navi text?)
    write_bits_to_save(0x00D4 + 0x02 * 0x1C + 0x04 + 0x0, 0x08) # Inside Jabu-Jabu's Belly switch flag (ruto?)
    write_bits_to_save(0x00D4 + 0x02 * 0x1C + 0x04 + 0x0, 0x04) # Inside Jabu-Jabu's Belly switch flag (ruto?)
    write_bits_to_save(0x00D4 + 0x02 * 0x1C + 0x04 + 0x0, 0x02) # Inside Jabu-Jabu's Belly switch flag (ruto?)
    write_bits_to_save(0x00D4 + 0x02 * 0x1C + 0x04 + 0x0, 0x01) # Inside Jabu-Jabu's Belly switch flag (ruto?)
    write_bits_to_save(0x00D4 + 0x02 * 0x1C + 0x04 + 0x1, 0x01) # Inside Jabu-Jabu's Belly switch flag (ruto?)
    write_bits_to_save(0x00D4 + 0x03 * 0x1C + 0x04 + 0x0, 0x08) # Forest Temple switch flag (poes?)
    write_bits_to_save(0x00D4 + 0x03 * 0x1C + 0x04 + 0x0, 0x01) # Forest Temple switch flag (poes?)
    write_bits_to_save(0x00D4 + 0x03 * 0x1C + 0x04 + 0x2, 0x02) # Forest Temple switch flag (poes?)
    write_bits_to_save(0x00D4 + 0x03 * 0x1C + 0x04 + 0x2, 0x01) # Forest Temple switch flag (poes?)
    write_bits_to_save(0x00D4 + 0x04 * 0x1C + 0x04 + 0x1, 0x08) # Fire Temple switch flag (First locked door?)
    write_bits_to_save(0x00D4 + 0x05 * 0x1C + 0x04 + 0x1, 0x01) # Water temple switch flag (navi text?)
    write_bits_to_save(0x00D4 + 0x0B * 0x1C + 0x04 + 0x2, 0x01) # Gerudo Training Ground switch flag (command text?)
    write_bits_to_save(0x00D4 + 0x51 * 0x1C + 0x04 + 0x2, 0x08) # Hyrule Field switch flag (???)
    write_bits_to_save(0x00D4 + 0x55 * 0x1C + 0x04 + 0x0, 0x80) # Kokiri Forest switch flag (???)
    write_bits_to_save(0x00D4 + 0x56 * 0x1C + 0x04 + 0x2, 0x40) # Sacred Forest Meadow switch flag (???)
    write_bits_to_save(0x00D4 + 0x5B * 0x1C + 0x04 + 0x2, 0x01) # Lost Woods switch flag (???)
    write_bits_to_save(0x00D4 + 0x5B * 0x1C + 0x04 + 0x3, 0x80) # Lost Woods switch flag (???)
    write_bits_to_save(0x00D4 + 0x5C * 0x1C + 0x04 + 0x0, 0x80) # Desert Colossus switch flag (???)
    write_bits_to_save(0x00D4 + 0x5F * 0x1C + 0x04 + 0x3, 0x20) # Hyrule Castle switch flag (???)

    write_bits_to_save(0x0ED4, 0x10) # "Met Deku Tree"
    write_bits_to_save(0x0ED5, 0x20) # "Deku Tree Opened Mouth"
    write_bits_to_save(0x0ED6, 0x08) # "Rented Horse From Ingo"
    write_bits_to_save(0x0EDA, 0x08) # "Began Nabooru Battle"
    write_bits_to_save(0x0EDC, 0x80) # "Entered the Master Sword Chamber"
    write_bits_to_save(0x0EDD, 0x20) # "Pulled Master Sword from Pedestal"
    write_bits_to_save(0x0EE0, 0x80) # "Spoke to Kaepora Gaebora by Lost Woods"
    write_bits_to_save(0x0EE7, 0x20) # "Nabooru Captured by Twinrova"
    write_bits_to_save(0x0EE7, 0x10) # "Spoke to Nabooru in Spirit Temple"
    write_bits_to_save(0x0EED, 0x20) # "Sheik, Spawned at Master Sword Pedestal as Adult"
    write_bits_to_save(0x0EED, 0x01) # "Nabooru Ordered to Fight by Twinrova"
    write_bits_to_save(0x0EF9, 0x01) # "Greeted by Saria"
    write_bits_to_save(0x0F0A, 0x04) # "Spoke to Ingo Once as Adult"
    write_bits_to_save(0x0F1A, 0x04) # "Met Darunia in Fire Temple"

    write_bits_to_save(0x0ED7, 0x01) # "Spoke to Child Malon at Castle or Market"
    write_bits_to_save(0x0ED7, 0x20) # "Spoke to Child Malon at Ranch"
    write_bits_to_save(0x0ED7, 0x40) # "Invited to Sing With Child Malon"
    write_bits_to_save(0x0F09, 0x10) # "Met Child Malon at Castle or Market"
    write_bits_to_save(0x0F09, 0x20) # "Child Malon Said Epona Was Scared of You"

    write_bits_to_save(0x0F21, 0x04) # "Ruto in JJ (M3) Talk First Time"
    write_bits_to_save(0x0F21, 0x02) # "Ruto in JJ (M2) Meet Ruto"

    write_bits_to_save(0x0EE2, 0x01) # "Began Ganondorf Battle"
    write_bits_to_save(0x0EE3, 0x80) # "Began Bongo Bongo Battle"
    write_bits_to_save(0x0EE3, 0x40) # "Began Barinade Battle"
    write_bits_to_save(0x0EE3, 0x20) # "Began Twinrova Battle"
    write_bits_to_save(0x0EE3, 0x10) # "Began Morpha Battle"
    write_bits_to_save(0x0EE3, 0x08) # "Began Volvagia Battle"
    write_bits_to_save(0x0EE3, 0x04) # "Began Phantom Ganon Battle"
    write_bits_to_save(0x0EE3, 0x02) # "Began King Dodongo Battle"
    write_bits_to_save(0x0EE3, 0x01) # "Began Gohma Battle"

    write_bits_to_save(0x0EE8, 0x01) # "Entered Deku Tree"
    write_bits_to_save(0x0EE9, 0x80) # "Entered Temple of Time"
    write_bits_to_save(0x0EE9, 0x40) # "Entered Goron City"
    write_bits_to_save(0x0EE9, 0x20) # "Entered Hyrule Castle"
    write_bits_to_save(0x0EE9, 0x10) # "Entered Zora's Domain"
    write_bits_to_save(0x0EE9, 0x08) # "Entered Kakariko Village"
    write_bits_to_save(0x0EE9, 0x02) # "Entered Death Mountain Trail"
    write_bits_to_save(0x0EE9, 0x01) # "Entered Hyrule Field"
    write_bits_to_save(0x0EEA, 0x04) # "Entered Ganon's Castle (Exterior)"
    write_bits_to_save(0x0EEA, 0x02) # "Entered Death Mountain Crater"
    write_bits_to_save(0x0EEA, 0x01) # "Entered Desert Colossus"
    write_bits_to_save(0x0EEB, 0x80) # "Entered Zora's Fountain"
    write_bits_to_save(0x0EEB, 0x40) # "Entered Graveyard"
    write_bits_to_save(0x0EEB, 0x20) # "Entered Jabu-Jabu's Belly"
    write_bits_to_save(0x0EEB, 0x10) # "Entered Lon Lon Ranch"
    write_bits_to_save(0x0EEB, 0x08) # "Entered Gerudo's Fortress"
    write_bits_to_save(0x0EEB, 0x04) # "Entered Gerudo Valley"
    write_bits_to_save(0x0EEB, 0x02) # "Entered Lake Hylia"
    write_bits_to_save(0x0EEB, 0x01) # "Entered Dodongo's Cavern"
    write_bits_to_save(0x0F08, 0x08) # "Entered Hyrule Castle"
 
    # Make all chest opening animations fast
    if world.fast_chests:
        rom.write_int32(0xBDA2E8, 0x240AFFFF) # addiu   t2, r0, -1
                               # replaces # lb      t2, 0x0002 (t1)

    # Set up for Rainbow Bridge dungeons condition
    Block_code = [0x15, 0x41, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x80, 0xEA, 0x00, 0xA5,
                  0x24, 0x01, 0x00, 0x1C, 0x31, 0x4A, 0x00, 0x1C, 0x08, 0x07, 0x88, 0xD9]
    rom.write_bytes(0x3480820, Block_code)

    # Gossip stones resond to stone of agony
    Block_code = [0x3C, 0x01, 0x80, 0x12, 0x80, 0x21, 0xA6, 0x75, 0x30, 0x21, 0x00, 0x20,
                  0x03, 0xE0, 0x00, 0x08]
    # Gossip stones always respond
    if(world.hints == 'always'):
        Block_code = [0x24, 0x01, 0x00, 0x20, 0x03, 0xE0, 0x00, 0x08]
    rom.write_bytes(0x3480840, Block_code)

    # Set up Rainbow Bridge conditions
    if world.bridge == 'medallions':
        Block_code = [0x80, 0xEA, 0x00, 0xA7, 0x24, 0x01, 0x00, 0x3F,
                      0x31, 0x4A, 0x00, 0x3F, 0x00, 0x00, 0x00, 0x00]
        rom.write_bytes(0xE2B454, Block_code)
    elif world.bridge == 'open':
        write_bits_to_save(0xEDC, 0x20) # "Rainbow Bridge Built by Sages"
    elif world.bridge == 'dungeons':
        Block_code = [0x80, 0xEA, 0x00, 0xA7, 0x24, 0x01, 0x00, 0x3F,
                      0x08, 0x10, 0x02, 0x08, 0x31, 0x4A, 0x00, 0x3F]
        rom.write_bytes(0xE2B454, Block_code)

    if world.open_forest:
        write_bits_to_save(0xED5, 0x10) # "Showed Mido Sword & Shield"

    if world.open_door_of_time:
        write_bits_to_save(0xEDC, 0x08) # "Opened the Door of Time"

    # "fast-ganon" stuff
    if world.no_escape_sequence:
        rom.write_bytes(0xD82A12, [0x05, 0x17]) # Sets exit from Ganondorf fight to entrance to Ganon fight
    if world.unlocked_ganondorf:
        write_bits_to_save(0x00D4 + 0x0A * 0x1C + 0x04 + 0x1, 0x10) # Ganon's Tower switch flag (unlock boss key door)
    if world.skipped_trials['Forest']:
        write_bits_to_save(0x0EEA, 0x08) # "Completed Forest Trial"
    if world.skipped_trials['Fire']:
        write_bits_to_save(0x0EEA, 0x40) # "Completed Fire Trial"
    if world.skipped_trials['Water']:
        write_bits_to_save(0x0EEA, 0x10) # "Completed Water Trial"
    if world.skipped_trials['Spirit']:
        write_bits_to_save(0x0EE8, 0x20) # "Completed Spirit Trial"
    if world.skipped_trials['Shadow']:
        write_bits_to_save(0x0EEA, 0x20) # "Completed Shadow Trial"
    if world.skipped_trials['Light']:
        write_bits_to_save(0x0EEA, 0x80) # "Completed Light Trial"
    if world.trials == 0:
        write_bits_to_save(0x0EED, 0x08) # "Dispelled Ganon's Tower Barrier"

    # open gerudo fortress
    if world.gerudo_fortress == 'open':
        write_bits_to_save(0x00A5, 0x40) # Give Gerudo Card
        write_bits_to_save(0x0EE7, 0x0F) # Free all 4 carpenters
        write_bits_to_save(0x00D4 + 0x0C * 0x1C + 0x04 + 0x1, 0x0F) # Thieves' Hideout switch flags (started all fights)
        write_bits_to_save(0x00D4 + 0x0C * 0x1C + 0x04 + 0x2, 0x01) # Thieves' Hideout switch flags (heard yells/unlocked doors)
        write_bits_to_save(0x00D4 + 0x0C * 0x1C + 0x04 + 0x3, 0xFE) # Thieves' Hideout switch flags (heard yells/unlocked doors)
        write_bits_to_save(0x00D4 + 0x0C * 0x1C + 0x0C + 0x2, 0xD4) # Thieves' Hideout collection flags (picked up keys, marks fights finished as well)
    elif world.gerudo_fortress == 'fast':
        write_bits_to_save(0x0EE7, 0x0E) # Free 3 carpenters
        write_bits_to_save(0x00D4 + 0x0C * 0x1C + 0x04 + 0x1, 0x0D) # Thieves' Hideout switch flags (started all fights)
        write_bits_to_save(0x00D4 + 0x0C * 0x1C + 0x04 + 0x2, 0x01) # Thieves' Hideout switch flags (heard yells/unlocked doors)
        write_bits_to_save(0x00D4 + 0x0C * 0x1C + 0x04 + 0x3, 0xDC) # Thieves' Hideout switch flags (heard yells/unlocked doors)
        write_bits_to_save(0x00D4 + 0x0C * 0x1C + 0x0C + 0x2, 0xC4) # Thieves' Hideout collection flags (picked up keys, marks fights finished as well)

    # Skip Epona race
    if world.no_epona_race:
        write_bits_to_save(0x0ED6, 0x01) # "Obtained Epona"
        rom.write_bytes(0xAD065C, [0x92, 0x42, 0x00, 0xA6, 0x30, 0x42, 0x00, 0x20]) # Epona spawning checks for Song

    # skip castle guard stealth sequence
    if world.no_guard_stealth:
        # change the exit at child/day crawlspace to the end of zelda's goddess cutscene
        rom.write_bytes(0x21F60DE, [0x05, 0xF0])


    messages = read_messages(rom)
    shop_items = read_shop_items(rom)
    remove_unused_messages(messages)

    # only one big poe needs to be caught to get the buyer's reward
    if world.only_one_big_poe:
        # change the value checked (in code) from 1000 to 100
        rom.write_bytes(0xEE69CE, [0x00, 0x64])
        # update dialogue
        update_message_by_id(messages, 0x70f7, "\x1AOh, you brought a Poe today!\x04\x1AHmmmm!\x04\x1AVery interesting!\x01This is a \x05\x41Big Poe\x05\x40!\x04\x1AI'll buy it for \x05\x4150 Rupees\x05\x40.\x04On top of that, I'll put \x05\x41100\x01points \x05\x40on your card.\x04\x1AIf you earn \x05\x41100 points\x05\x40, you'll\x01be a happy man! Heh heh.")
        update_message_by_id(messages, 0x70f8, "\x1AWait a minute! WOW!\x04\x1AYou have earned \x05\x41100 points\x05\x40!\x04\x1AYoung man, you are a genuine\x01\x05\x41Ghost Hunter\x05\x40!\x04\x1AIs that what you expected me to\x01say? Heh heh heh!\x04\x1ABecause of you, I have extra\x01inventory of \x05\x41Big Poes\x05\x40, so this will\x01be the last time I can buy a \x01ghost.\x04\x1AYou're thinking about what I \x01promised would happen when you\x01earned 100 points. Heh heh.\x04\x1ADon't worry, I didn't forget.\x01Just take this.")

    # Sets hooks for gossip stone changes
    if world.hints != 'none':
        if world.hints != 'mask':
            rom.write_bytes(0xEE7B84, [0x0C, 0x10, 0x02, 0x10])
            rom.write_bytes(0xEE7B8C, [0x24, 0x02, 0x00, 0x20])
        buildGossipHints(world, messages)

    # Set hints for boss reward shuffle
    rom.write_bytes(0xE2ADB2, [0x70, 0x7A])
    rom.write_bytes(0xE2ADB6, [0x70, 0x57])
    buildBossRewardHints(world, messages)

    # build silly ganon lines
    buildGanonText(world, messages)

    # Write item overrides
    override_table = get_override_table(world)
    rom.write_bytes(0x3481000, sum(override_table, []))
    rom.write_byte(0x03481C00, world.id + 1) # Write player ID

    # Revert Song Get Override Injection
    if not world.shuffle_song_items:
        rom.write_bytes(0xAE5DE0, [0x00, 0x07, 0x70, 0x80, 0x3C, 0x0D, 0x80, 0x10, 0x25, 0x08, 0xA5, 0xD0])

    # Set default targeting option to Hold
    if world.default_targeting == 'hold':
        rom.write_byte(0xB71E6D, 0x01)

    # Patch songs and boss rewards
    for location in world.get_locations():
        item = location.item
        itemid = item.code
        locationaddress = location.address
        secondaryaddress = location.address2

        if itemid is None or location.address is None:
            continue

        if location.type == 'Song':
            rom.write_byte(locationaddress, itemid)
            itemid = itemid + 0x0D
            rom.write_byte(secondaryaddress, itemid)
            if location.name == 'Impa at Castle':
                impa_fix = 0x65 - item.index
                rom.write_byte(0xD12ECB, impa_fix)
                impa_fix = 0x8C34 - (item.index * 4)
                impa_fix_high = impa_fix >> 8
                impa_fix_low = impa_fix & 0x00FF
                rom.write_bytes(0xB063FE, [impa_fix_high, impa_fix_low])
                rom.write_byte(0x2E8E931, item_data[item.name]) #Fix text box
            elif location.name == 'Song from Malon':
                if item.name == 'Suns Song':
                    rom.write_byte(locationaddress, itemid)
                malon_fix = 0x8C34 - (item.index * 4)
                malon_fix_high = malon_fix >> 8
                malon_fix_low = malon_fix & 0x00FF
                rom.write_bytes(0xD7E142, [malon_fix_high, malon_fix_low])
                rom.write_bytes(0xD7E8D6, [malon_fix_high, malon_fix_low]) # I really don't like hardcoding these addresses, but for now.....
                rom.write_bytes(0xD7E786, [malon_fix_high, malon_fix_low])
                rom.write_byte(0x29BECB9, item_data[item.name]) #Fix text box
            elif location.name == 'Song from Composer Grave':
                sun_fix = 0x8C34 - (item.index * 4)
                sun_fix_high = sun_fix >> 8
                sun_fix_low = sun_fix & 0x00FF
                rom.write_bytes(0xE09F66, [sun_fix_high, sun_fix_low])
                rom.write_byte(0x332A87D, item_data[item.name]) #Fix text box
            elif location.name == 'Song from Saria':
                saria_fix = 0x65 - item.index
                rom.write_byte(0xE2A02B, saria_fix)
                saria_fix = 0x8C34 - (item.index * 4)
                saria_fix_high = saria_fix >> 8
                saria_fix_low = saria_fix & 0x00FF
                rom.write_bytes(0xE29382, [saria_fix_high, saria_fix_low])
                rom.write_byte(0x20B1DBD, item_data[item.name]) #Fix text box
            elif location.name == 'Song from Ocarina of Time':
                rom.write_byte(0x252FC95, item_data[item.name]) #Fix text box
            elif location.name == 'Song at Windmill':
                windmill_fix = 0x65 - item.index
                rom.write_byte(0xE42ABF, windmill_fix)
                rom.write_byte(0x3041091, item_data[item.name]) #Fix text box
            elif location.name == 'Sheik Forest Song':
                minuet_fix = 0x65 - item.index
                rom.write_byte(0xC7BAA3, minuet_fix)
                rom.write_byte(0x20B0815, item_data[item.name]) #Fix text box
            elif location.name == 'Sheik at Temple':
                prelude_fix = 0x65 - item.index
                rom.write_byte(0xC805EF, prelude_fix)
                rom.write_byte(0x2531335, item_data[item.name]) #Fix text box
            elif location.name == 'Sheik in Crater':
                bolero_fix = 0x65 - item.index
                rom.write_byte(0xC7BC57, bolero_fix)
                rom.write_byte(0x224D7FD, item_data[item.name]) #Fix text box
            elif location.name == 'Sheik in Ice Cavern':
                serenade_fix = 0x65 - item.index
                rom.write_byte(0xC7BD77, serenade_fix)
                rom.write_byte(0x2BEC895, item_data[item.name]) #Fix text box
            elif location.name == 'Sheik in Kakariko':
                nocturne_fix = 0x65 - item.index
                rom.write_byte(0xAC9A5B, nocturne_fix)
                rom.write_byte(0x2000FED, item_data[item.name]) #Fix text box
            elif location.name == 'Sheik at Colossus':
                rom.write_byte(0x218C589, item_data[item.name]) #Fix text box
        elif location.type == 'Boss':
            if location.name == 'Links Pocket':
                write_bits_to_save(item_data[item.name][1], item_data[item.name][0])
            else:
                rom.write_byte(locationaddress, itemid)
                rom.write_byte(secondaryaddress, item_data[item.name][2])
                if location.name == 'Bongo Bongo':
                    rom.write_bytes(0xCA3F32, [item_data[item.name][3][0], item_data[item.name][3][1]])
                    rom.write_bytes(0xCA3F36, [item_data[item.name][3][2], item_data[item.name][3][3]])
                elif location.name == 'Twinrova':
                    rom.write_bytes(0xCA3EA2, [item_data[item.name][3][0], item_data[item.name][3][1]])
                    rom.write_bytes(0xCA3EA6, [item_data[item.name][3][2], item_data[item.name][3][3]])

    if world.bombchus_in_logic:
        # add a cheaper bombchu pack to the bombchu shop
        # describe
        add_message(messages, '\x08\x05\x41Bombchu   (5 pieces)   60 Rupees\x01\x05\x40This looks like a toy mouse, but\x01it\'s actually a self-propelled time\x01bomb!\x09\x0A', 0x80FE, 0x03)
        # purchase
        add_message(messages, '\x08Bombchu    5 Pieces    60 Rupees\x01\x01\x1B\x05\x42Buy\x01Don\'t buy\x05\x40\x09', 0x80FF, 0x03)
        rbl_bombchu = shop_items[0x0018]
        rbl_bombchu.price = 60
        rbl_bombchu.pieces = 5
        rbl_bombchu.get_item_id = 0x006A
        rbl_bombchu.description_message = 0x80FE
        rbl_bombchu.purchase_message = 0x80FF

        #Fix bombchu chest animations
        chestAnimations = {
            0x6A: 0x28, #0xD8 #Bombchu (5) 
            0x03: 0x28, #0xD8 #Bombchu (10)    
            0x6B: 0x28, #0xD8 #Bombchu (20)    
        }
        for item_id, gfx_id in chestAnimations.items():
            rom.write_byte(0xBEEE8E + (item_id * 6) + 2, gfx_id)

    #Fix item chest animations
    chestAnimations = {
        0x3D: 0xED, #0x13 #Heart Container 
        0x3E: 0xEC, #0x14 #Piece of Heart  
        0x42: 0x02, #0xFE #Small Key   
        0x48: 0xF7, #0x09 #Recovery Heart  
        0x4F: 0xED, #0x13 #Heart Container 
    }
    for item_id, gfx_id in chestAnimations.items():
        rom.write_byte(0xBEEE8E + (item_id * 6) + 2, gfx_id)

    # Update chest type sizes
    if world.correct_chest_sizes:
        update_chest_sizes(rom, override_table)

    # give dungeon items the correct messages
    message_patch_for_dungeon_items(messages, shop_items, world)

    # reduce item message lengths
    update_item_messages(messages, world)

    repack_messages(rom, messages)
    write_shop_items(rom, shop_items)

    # text shuffle
    if world.text_shuffle == 'except_hints':
        shuffle_messages(rom, True)
    elif world.text_shuffle == 'complete':
        shuffle_messages(rom, False)

    # output a text dump, for testing...
    #with open('keysanity_' + str(world.seed) + '_dump.txt', 'w', encoding='utf-16') as f:
    #     messages = read_messages(rom)
    #     f.write('item_message_strings = {\n')
    #     for m in messages:
    #        f.write("\t0x%04X: \"%s\",\n" % (m.id, m.get_python_string()))
    #     f.write('}\n')


    scarecrow_song = None
    if world.free_scarecrow:
        original_songs = [
            'LURLUR',
            'ULRULR',
            'DRLDRL',
            'RDURDU',
            'RADRAD',
            'ADUADU',
            'AULRLR',
            'DADALDLD',
            'ADRRL',
            'ADALDA',
            'LRRALRD',
            'URURLU'
        ]

        note_map = {
            'A': 0,
            'D': 1,
            'R': 2,
            'L': 3,
            'U': 4
        }

        if len(world.scarecrow_song) != 8:
            raise Exception('Scarecrow Song must be 8 notes long')

        if len(set(world.scarecrow_song.upper())) == 1:
            raise Exception('Scarecrow Song must contain at least two different notes')           

        notes = []
        for c in world.scarecrow_song.upper():
            if c not in note_map:
                raise Exception('Invalid note %s. Valid notes are A, D, R, L, U' % c)

            notes.append(note_map[c])
        scarecrow_song = Song(activation=notes)

        if not world.ocarina_songs:
            for original_song in original_songs:
                song_notes = []
                for c in original_song:
                    song_notes.append(note_map[c])
                song = Song(activation=song_notes)

                if subsong(scarecrow_song, song):
                    raise Exception('You may not have the Scarecrow Song contain an existing song')

        write_bits_to_save(0x0EE6, 0x10)     # Played song as adult
        write_byte_to_save(0x12C5, 0x01)    # Song is remembered
        write_bytes_to_save(0x12C6, scarecrow_song.playback_data[:(16*8)], lambda v: v != 0)

    if world.ocarina_songs:
        replace_songs(rom, scarecrow_song)

    # actually write the save table to rom
    write_save_table(rom)

    # re-seed for aesthetic effects. They shouldn't be affected by the generation seed
    random.seed()

    # patch tunic colors
    # Custom color tunic stuff
    Tunics = []
    Tunics.append(0x00B6DA38) # Kokiri Tunic
    Tunics.append(0x00B6DA3B) # Goron Tunic
    Tunics.append(0x00B6DA3E) # Zora Tunic
    colorList = get_tunic_colors()
    randomColors = random.choices(colorList, k=3)

    for i in range(len(Tunics)):
        # get the color option
        thisColor = world.tunic_colors[i]
        # handle true random
        randColor = [random.getrandbits(8), random.getrandbits(8), random.getrandbits(8)]
        if thisColor == 'Completely Random':
            color = randColor
        else:
            # handle random
            if world.tunic_colors[i] == 'Random Choice':
                thisColor = randomColors[i]
            # grab the color from the list
            color = TunicColors[thisColor]
        rom.write_bytes(Tunics[i], color)

    # patch navi colors
    Navi = []
    Navi.append([0x00B5E184]) # Default
    Navi.append([0x00B5E19C, 0x00B5E1BC]) # Enemy, Boss
    Navi.append([0x00B5E194]) # NPC
    Navi.append([0x00B5E174, 0x00B5E17C, 0x00B5E18C, 0x00B5E1A4, 0x00B5E1AC, 0x00B5E1B4, 0x00B5E1C4, 0x00B5E1CC, 0x00B5E1D4]) # Everything else
    naviList = get_navi_colors()
    randomColors = random.choices(naviList, k=4)

    for i in range(len(Navi)):
        # do everything in the inner loop so that "true random" changes even for subcategories
        for j in range(len(Navi[i])):
            # get the color option
            thisColor = world.navi_colors[i]
            # handle true random
            randColor = [random.getrandbits(8), random.getrandbits(8), random.getrandbits(8), 0xFF,
                         random.getrandbits(8), random.getrandbits(8), random.getrandbits(8), 0x00]
            if thisColor == 'Completely Random':
                color = randColor
            else:
                # handle random
                if world.navi_colors[i] == 'Random Choice':
                    thisColor = randomColors[i]
                # grab the color from the list
                color = NaviColors[thisColor]
            rom.write_bytes(Navi[i][j], color)

    #Low health beep
    healthSFXList = ['Default', 'Softer Beep', 'Rupee', 'Timer', 'Tamborine', 'Recovery Heart', 'Carrot Refill', 'Navi - Hey!', 'Zelda - Gasp', 'Cluck', 'Mweep!', 'None']
    randomSFX = random.choice(healthSFXList)
    address = 0xADBA1A
    
    if world.healthSFX == 'Random Choice':
        thisHealthSFX = randomSFX
    else:
        thisHealthSFX = world.healthSFX
    if thisHealthSFX == 'Default':
        healthSFX = [0x48, 0x1B]
    elif thisHealthSFX == 'Softer Beep':
        healthSFX = [0x48, 0x04]
    elif thisHealthSFX == 'Rupee':
        healthSFX = [0x48, 0x03]
    elif thisHealthSFX == 'Timer':
        healthSFX = [0x48, 0x1A]
    elif thisHealthSFX == 'Tamborine':
        healthSFX = [0x48, 0x42]
    elif thisHealthSFX == 'Recovery Heart':
        healthSFX = [0x48, 0x0B]
    elif thisHealthSFX == 'Carrot Refill':
        healthSFX = [0x48, 0x45]
    elif thisHealthSFX == 'Navi - Hey!':
        healthSFX = [0x68, 0x5F]
    elif thisHealthSFX == 'Zelda - Gasp':
        healthSFX = [0x68, 0x79]
    elif thisHealthSFX == 'Cluck':
        healthSFX = [0x28, 0x12]
    elif thisHealthSFX == 'Mweep!':
        healthSFX = [0x68, 0x7A]
    elif thisHealthSFX == 'None':
        healthSFX = [0x00, 0x00, 0x00, 0x00]
        address = 0xADBA14
    rom.write_bytes(address, healthSFX)
        
    return rom

def get_override_table(world):
    override_entries = []
    for location in world.get_locations():
        override_entries.append(get_override_entry(location))
    override_entries.sort()
    return override_entries

def get_override_entry(location):
    scene = location.scene
    default = location.default
    item_id = location.item.index
    if None in [scene, default, item_id]:
        return []

    player_id = (location.item.world.id + 1) << 3

    if location.type in ['NPC', 'BossHeart']:
        return [scene, player_id | 0x00, default, item_id]
    elif location.type == 'Chest':
        flag = default & 0x1F
        return [scene, player_id | 0x01, flag, item_id]
    elif location.type == 'Collectable':
        return [scene, player_id | 0x02, default, item_id]
    elif location.type == 'GS Token':
        return [scene, player_id | 0x03, default, item_id]
    else:
        return []


chestTypeMap = {
        #    small   big     boss
    0x0000: [0x5000, 0x0000, 0x2000], #Large
    0x1000: [0x7000, 0x1000, 0x1000], #Large, Appears, Clear Flag
    0x2000: [0x5000, 0x0000, 0x2000], #Boss Key’s Chest
    0x3000: [0x8000, 0x3000, 0x3000], #Large, Falling, Switch Flag
    0x4000: [0x6000, 0x4000, 0x4000], #Large, Invisible
    0x5000: [0x5000, 0x0000, 0x2000], #Small
    0x6000: [0x6000, 0x4000, 0x4000], #Small, Invisible
    0x7000: [0x7000, 0x1000, 0x1000], #Small, Appears, Clear Flag
    0x8000: [0x8000, 0x3000, 0x3000], #Small, Falling, Switch Flag
    0x9000: [0x9000, 0x9000, 0x9000], #Large, Appears, Zelda's Lullaby
    0xA000: [0xA000, 0xA000, 0xA000], #Large, Appears, Sun's Song Triggered
    0xB000: [0xB000, 0xB000, 0xB000], #Large, Appears, Switch Flag
    0xC000: [0x5000, 0x0000, 0x2000], #Large
    0xD000: [0x5000, 0x0000, 0x2000], #Large
    0xE000: [0x5000, 0x0000, 0x2000], #Large
    0xF000: [0x5000, 0x0000, 0x2000], #Large
}

chestAnimationExtendedFast = [
    0x87, # Progressive Nut Capacity
    0x88, # Progressive Stick Capacity
    0xB6, # Recovery Heart
    0xB7, # Arrows (5)
    0xB8, # Arrows (10)
    0xB9, # Arrows (30)
    0xBA, # Bombs (5)
    0xBB, # Bombs (10)
    0xBC, # Bombs (20)
    0xBD, # Deku Nuts (5)
    0xBE, # Deku Nuts (10)
]


def room_get_chests(rom, room_data, scene, chests, alternate=None):
    room_start = alternate or room_data
    command = 0
    while command != 0x14: # 0x14 = end header
        command = rom.read_byte(room_data)
        if command == 0x01: # actor list
            actor_count = rom.read_byte(room_data + 1)
            actor_list = room_start + (rom.read_int32(room_data + 4) & 0x00FFFFFF)
            for _ in range(0, actor_count):
                actor_id = rom.read_int16(actor_list);
                actor_var = rom.read_int16(actor_list + 14)
                if actor_id == 0x000A: #Chest Actor
                    chests[actor_list + 14] = [scene, actor_var & 0x001F]
                actor_list = actor_list + 16
        if command == 0x18 and scene >= 81 and scene <= 99: # Alternate header list
            header_list = room_start + (rom.read_int32(room_data + 4) & 0x00FFFFFF)
            for alt_id in range(0,2):
                header_data = room_start + (rom.read_int32(header_list + 4) & 0x00FFFFFF)
                if header_data != 0 and not alternate:
                    room_get_chests(rom, header_data, scene, chests, room_start)
                header_list = header_list + 4
        room_data = room_data + 8


def scene_get_chests(rom, scene_data, scene, chests, alternate=None):
    scene_start = alternate or scene_data
    command = 0
    while command != 0x14: # 0x14 = end header
        command = rom.read_byte(scene_data)
        if command == 0x04: #room list
            room_count = rom.read_byte(scene_data + 1)
            room_list = scene_start + (rom.read_int32(scene_data + 4) & 0x00FFFFFF)
            for _ in range(0, room_count):
                room_data = rom.read_int32(room_list);
                room_get_chests(rom, room_data, scene, chests)
                room_list = room_list + 8
        if command == 0x18 and scene >= 81 and scene <= 99: # Alternate header list
            header_list = scene_start + (rom.read_int32(scene_data + 4) & 0x00FFFFFF)
            for alt_id in range(0,2):
                header_data = scene_start + (rom.read_int32(header_list + 4) & 0x00FFFFFF)
                if header_data != 0 and not alternate:
                    scene_get_chests(rom, header_data, scene, chests, scene_start)
                header_list = header_list + 4

        scene_data = scene_data + 8


def get_chest_list(rom):
    chests = {}
    scene_table = 0x00B71440
    for scene in range(0x00, 0x65):
        scene_data = rom.read_int32(scene_table + (scene * 0x14));
        scene_get_chests(rom, scene_data, scene, chests)
    return chests


def get_override_itemid(override_table, scene, type, flags):
    for entry in override_table:
        if len(entry) == 4 and entry[0] == scene and (entry[1] & 0x07) == type and entry[2] == flags:
            return entry[3]
    return None

def update_chest_sizes(rom, override_table):
    chest_list = get_chest_list(rom)
    for address, [scene, flags] in chest_list.items():
        item_id = get_override_itemid(override_table, scene, 1, flags)

        if None in [address, scene, flags, item_id]:
            continue

        itemType = 0  # Item animation

        if item_id >= 0x80: # if extended item, always big except from exception list
            itemType = 0 if item_id in chestAnimationExtendedFast else 1
        elif rom.read_byte(0xBEEE8E + (item_id * 6) + 2) & 0x80: # get animation from rom, ice trap is big
            itemType = 0 # No animation, small chest
        else:
            itemType = 1 # Long animation, big chest
        # Don't use boss chests

        default = rom.read_int16(address)
        chestType = default & 0xF000
        newChestType = chestTypeMap[chestType][itemType]
        default = (default & 0x0FFF) | newChestType
        rom.write_int16(address, default)
