import logging

import pytest
from cu2qu.ufo import font_to_quadratic
from fontTools.pens.hashPointPen import HashPointPen
from fontTools.ttLib.ttFont import TTFont

from ufo2ft.instructionCompiler import InstructionCompiler

from .outlineCompiler_test import getpath


def get_hash_ufo(glyph, ufo):
    hash_pen = HashPointPen(glyph.width, ufo)
    glyph.drawPoints(hash_pen)
    return hash_pen.hash


def get_hash_ttf(glyph_name, ttf):
    aw, _lsb = ttf["hmtx"][glyph_name]
    gs = ttf.getGlyphSet()
    hash_pen = HashPointPen(aw, gs)
    ttf["glyf"][glyph_name].drawPoints(hash_pen, ttf["glyf"])
    return hash_pen.hash


@pytest.fixture
def quadfont():
    font = TTFont()
    font.importXML(getpath("Testfont-TTF-post3.ttx"))
    return font


@pytest.fixture
def quadufo(FontClass):
    font = FontClass(getpath("TestFont.ufo"))
    font_to_quadratic(font)
    return font


@pytest.fixture
def quaduforeversed(FontClass):
    font = FontClass(getpath("TestFont.ufo"))
    font_to_quadratic(font=font, reverse_direction=True)
    return font


@pytest.fixture
def testufo(FontClass):
    font = FontClass(getpath("TestFont.ufo"))
    del font.lib["public.postscriptNames"]
    return font


class InstructionCompilerTest:

    # _check_glyph_hash

    def test_check_glyph_hash_match(self, quaduforeversed, quadfont):
        glyph = quaduforeversed["a"]
        ufo_hash = get_hash_ufo(glyph, quaduforeversed)
        ttglyph = quadfont["glyf"]["a"]

        result = InstructionCompiler()._check_glyph_hash(
            glyph=glyph,
            ttglyph=ttglyph,
            glyph_hash=ufo_hash,
            otf=quadfont,
        )
        assert result

    def test_check_glyph_hash_missing(self, quaduforeversed, quadfont):
        glyph = quaduforeversed["a"]

        result = InstructionCompiler()._check_glyph_hash(
            glyph=glyph,
            ttglyph=quadfont["glyf"]["a"],
            glyph_hash=None,
            otf=quadfont,
        )
        assert not result

    def test_check_glyph_hash_mismatch(self, testufo, quadfont):
        glyph = testufo["a"]
        ufo_hash = get_hash_ufo(glyph, testufo)
        ttglyph = quadfont["glyf"]["a"]

        # The contour direction is reversed in testufo vs. quadfont, so the
        # hash should not match

        result = InstructionCompiler()._check_glyph_hash(
            glyph=glyph,
            ttglyph=ttglyph,
            glyph_hash=ufo_hash,
            otf=quadfont,
        )
        assert not result

    def test_check_glyph_hash_mismatch_width(self, quaduforeversed, quadfont):
        glyph = quaduforeversed["a"]

        # Modify the glyph width in the UFO to trigger the mismatch
        glyph.width += 10

        ufo_hash = get_hash_ufo(glyph, quaduforeversed)
        ttglyph = quadfont["glyf"]["a"]

        result = InstructionCompiler()._check_glyph_hash(
            glyph=glyph,
            ttglyph=ttglyph,
            glyph_hash=ufo_hash,
            otf=quadfont,
        )
        assert not result

    # _check_tt_data_format

    def test_check_tt_data_format_match_str(self):
        result = InstructionCompiler()._check_tt_data_format(
            ttdata={"formatVersion": "1"},
            name="",
        )
        assert result is None

    def test_check_tt_data_format_type_error(self):
        with pytest.raises(
            TypeError,
            match="Illegal type 'int' instead of 'str' for formatVersion for instructions in location.",
        ):
            InstructionCompiler()._check_tt_data_format(
                ttdata={"formatVersion": 1},  # Spec requires a str
                name="location",
            )

    def test_check_tt_data_format_mismatch_str(self):
        with pytest.raises(
            NotImplementedError,
            match="Unknown formatVersion 1.5 for instructions in location.",
        ):
            InstructionCompiler()._check_tt_data_format(
                ttdata={"formatVersion": "1.5"},  # Maps to the correct int
                name="location",
            )

    # _compile_program

    def test_compile_program_invalid_tag(self):
        with pytest.raises(AssertionError):
            # table_tag must be "fpgm" or "prep"
            InstructionCompiler()._compile_program(key="foo", table_tag="bar")

    def test_compile_program_no_ttdata(self, quadufo):
        # UFO contains no "public.truetype.instructions" lib key
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        for key, tag in (
            ("controlValueProgram", "prep"),
            ("fontProgram", "fpgm"),
        ):
            ic._compile_program(key=key, table_tag=tag)
        assert "fpgm" not in ic.otf
        assert "prep" not in ic.otf

    def test_compile_program_no_programs(self, quadufo):
        # UFO contains the "public.truetype.instructions" lib key, but the font and
        # control value programs are not there. (They are optional)
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.ufo.lib["public.truetype.instructions"] = {
            "formatVersion": "1",
        }
        for key, tag in (
            ("controlValueProgram", "prep"),
            ("fontProgram", "fpgm"),
        ):
            ic._compile_program(key=key, table_tag=tag)
        assert "fpgm" not in ic.otf
        assert "prep" not in ic.otf

    def test_compile_program_none(self, quadufo):
        # UFO contains the "public.truetype.instructions" lib key, but the font and
        # control value programs are None.
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.ufo.lib["public.truetype.instructions"] = {
            "formatVersion": "1",
            "controlValueProgram": None,
            "fontProgram": None,
        }
        for key, tag in (
            ("controlValueProgram", "prep"),
            ("fontProgram", "fpgm"),
        ):
            ic._compile_program(key=key, table_tag=tag)
        assert "fpgm" not in ic.otf
        assert "prep" not in ic.otf

    def test_compile_program_empty(self, quadufo):
        # UFO contains the "public.truetype.instructions" lib key, but the font and
        # control value programs are empty.
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.ufo.lib["public.truetype.instructions"] = {
            "formatVersion": "1",
            "controlValueProgram": "",
            "fontProgram": "",
        }
        for key, tag in (
            ("controlValueProgram", "prep"),
            ("fontProgram", "fpgm"),
        ):
            ic._compile_program(key=key, table_tag=tag)
        assert "fpgm" not in ic.otf
        assert "prep" not in ic.otf

    def test_compile_program(self, quadufo):
        # UFO contains the "public.truetype.instructions" lib key, and the font and
        # control value programs are present.
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.ufo.lib["public.truetype.instructions"] = {
            "formatVersion": "1",
            "controlValueProgram": "PUSHW[]\n511\nSCANCTRL[]",
            "fontProgram": "PUSHB[]\n0\nFDEF[]\nPOP[]\nENDF[]",
        }
        for key, tag in (
            ("controlValueProgram", "prep"),
            ("fontProgram", "fpgm"),
        ):
            ic._compile_program(key=key, table_tag=tag)

        assert "fpgm" in ic.otf
        assert "prep" in ic.otf

        # Check if the bytecode is correct, though this may be out of scope
        assert ic.otf["fpgm"].program.getBytecode() == b"\xb0\x00\x2C\x21\x2D"
        assert ic.otf["prep"].program.getBytecode() == b"\xb8\x01\xff\x85"

    # compileGlyphInstructions

    def test_compileGlyphInstructions_missing_glyph(self, caplog):
        # The method logs an info when trying to compile a glyph which is
        # missing in the UFO, e.g. '.notdef'
        ic = InstructionCompiler()
        ic.ufo = dict()
        with caplog.at_level(
            logging.INFO, logger="ufo2ft.instructionCompiler"
        ):
            ic.compileGlyphInstructions(None, "A")
        assert (
            "Skipping compilation of instructions for glyph 'A'" in caplog.text
        )

    # _compile_tt_glyph_program

    def test_compile_tt_glyph_program_empty(self, quaduforeversed, quadfont):
        # UFO glyph contains no "public.truetype.instructions" lib key
        with pytest.raises(
            TypeError,
            match="Illegal type 'NoneType' instead of 'str' for formatVersion for instructions in glyph 'a'.",
        ):
            InstructionCompiler()._compile_tt_glyph_program(
                glyph=quaduforeversed["a"],
                ttglyph=quadfont["glyf"]["a"],
                ttdata={},
            )

    def test_compile_tt_glyph_program_no_asm(self, quaduforeversed, quadfont, caplog):
        # UFO glyph contains "public.truetype.instructions" lib key, but no
        # assembly code entry
        ic = InstructionCompiler()
        ic.ufo = quaduforeversed
        ic.otf = quadfont

        assert not ic.otf["glyf"]["a"].isComposite()

        glyph = ic.ufo["a"]
        glyph_hash = get_hash_ufo(glyph, ic.ufo)

        with caplog.at_level(logging.ERROR, logger="ufo2ft.instructionCompiler"):
            ic._compile_tt_glyph_program(
                glyph=ic.ufo["a"],
                ttglyph=ic.otf["glyf"]["a"],
                ttdata={
                    "formatVersion": "1",
                    "id": glyph_hash,
                    # "assembly": "",
                },
            )
        assert (
            "Glyph assembly missing, glyph 'a' will have no instructions in font."
            in caplog.text
        )

    def test_compile_tt_glyph_program_empty_asm(self, quaduforeversed, quadfont):
        # UFO glyph contains "public.truetype.instructions" lib key, but the
        # assembly code entry is empty
        ic = InstructionCompiler()
        ic.ufo = quaduforeversed
        ic.otf = quadfont

        assert not ic.otf["glyf"]["a"].isComposite()

        glyph = ic.ufo["a"]
        glyph_hash = get_hash_ufo(glyph, ic.ufo)

        ic._compile_tt_glyph_program(
            glyph=ic.ufo["a"],
            ttglyph=ic.otf["glyf"]["a"],
            ttdata={
                "formatVersion": "1",
                "id": glyph_hash,
                "assembly": "",
            },
        )
        # assert ic.otf["glyf"]["a"].program.getBytecode() == b""
        assert not hasattr(ic.otf["glyf"]["h"], "program")

    def test_compile_tt_glyph_program_empty_asm_composite(self, quaduforeversed, quadfont):
        # UFO glyph contains "public.truetype.instructions" lib key, but the
        # assembly code entry is empty. The glyph is a composite.
        ic = InstructionCompiler()
        ic.ufo = quaduforeversed
        ic.otf = quadfont

        glyph = ic.ufo["h"]
        glyph_hash = get_hash_ufo(glyph, ic.ufo)

        assert ic.otf["glyf"]["h"].isComposite()

        ic._compile_tt_glyph_program(
            glyph=ic.ufo["h"],
            ttglyph=ic.otf["glyf"]["h"],
            ttdata={
                "formatVersion": "1",
                "id": glyph_hash,
                "assembly": "",
            },
        )
        # Components must not have an empty program
        assert not hasattr(ic.otf["glyf"]["h"], "program")

    def test_compile_tt_glyph_program(self, quaduforeversed, quadfont):
        # UFO glyph contains "public.truetype.instructions" lib key, and the
        # assembly code entry is present.
        ic = InstructionCompiler()
        ic.ufo = quaduforeversed
        ic.otf = quadfont

        assert not ic.otf["glyf"]["a"].isComposite()

        glyph = ic.ufo["a"]
        glyph_hash = get_hash_ufo(glyph, ic.ufo)

        ic._compile_tt_glyph_program(
            glyph=ic.ufo["a"],
            ttglyph=ic.otf["glyf"]["a"],
            ttdata={
                "formatVersion": "1",
                "id": glyph_hash,
                "assembly": "PUSHB[]\n0\nMDAP[1]",
            },
        )
        assert ic.otf["glyf"]["a"].program.getBytecode() == b"\xb0\x00\x2f"

    # _set_composite_flags

    def test_set_composite_flags(self):
        pass

    # update_maxp

    def test_update_maxp(self):
        pass

    # setupTable_cvt

    def test_setupTable_cvt(self):
        pass

    # setupTable_fpgm

    def test_setupTable_fpgm_no_ttdata(self, quadufo):
        # UFO contains no "public.truetype.instructions" lib key
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.setupTable_fpgm()
        assert "fpgm" not in ic.otf

    def test_setupTable_fpgm_no_program(self, quadufo):
        # UFO contains the "public.truetype.instructions" lib key, but the font and
        # control value programs are not there. (They are optional)
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.ufo.lib["public.truetype.instructions"] = {
            "formatVersion": "1",
        }
        ic.setupTable_fpgm()
        assert "fpgm" not in ic.otf

    def test_setupTable_fpgm_none(self, quadufo):
        # UFO contains the "public.truetype.instructions" lib key, but the font and
        # control value programs are None.
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.ufo.lib["public.truetype.instructions"] = {
            "formatVersion": "1",
            "fontProgram": None,
        }
        ic.setupTable_fpgm()
        assert "fpgm" not in ic.otf

    def test_setupTable_fpgm_empty(self, quadufo):
        # UFO contains the "public.truetype.instructions" lib key, but the font and
        # control value programs are empty.
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.ufo.lib["public.truetype.instructions"] = {
            "formatVersion": "1",
            "fontProgram": "",
        }
        ic.setupTable_fpgm()
        assert "fpgm" not in ic.otf

    def test_setupTable_fpgm(self, quadufo):
        # UFO contains the "public.truetype.instructions" lib key, and the font and
        # control value programs are present.
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.ufo.lib["public.truetype.instructions"] = {
            "formatVersion": "1",
            "fontProgram": "PUSHB[]\n0\nFDEF[]\nPOP[]\nENDF[]",
        }
        ic.setupTable_fpgm()

        assert "fpgm" in ic.otf

        # Check if the bytecode is correct, though this may be out of scope
        assert ic.otf["fpgm"].program.getBytecode() == b"\xb0\x00\x2C\x21\x2D"

    # setupTable_prep

    def test_setupTable_prep_no_ttdata(self, quadufo):
        # UFO contains no "public.truetype.instructions" lib key
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.setupTable_prep()
        assert "prep" not in ic.otf

    def test_setupTable_prep_no_program(self, quadufo):
        # UFO contains the "public.truetype.instructions" lib key, but the font and
        # control value programs are not there. (They are optional)
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.ufo.lib["public.truetype.instructions"] = {
            "formatVersion": "1",
        }
        ic.setupTable_prep()
        assert "prep" not in ic.otf

    def test_setupTable_prep_none(self, quadufo):
        # UFO contains the "public.truetype.instructions" lib key, but the font and
        # control value programs are None.
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.ufo.lib["public.truetype.instructions"] = {
            "formatVersion": "1",
            "controlValueProgram": None,
        }
        ic.setupTable_prep()
        assert "prep" not in ic.otf

    def test_setupTable_prep_empty(self, quadufo):
        # UFO contains the "public.truetype.instructions" lib key, but the font and
        # control value programs are empty.
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.ufo.lib["public.truetype.instructions"] = {
            "formatVersion": "1",
            "controlValueProgram": "",
        }
        ic.setupTable_prep()
        assert "prep" not in ic.otf

    def test_setupTable_prep(self, quadufo):
        # UFO contains the "public.truetype.instructions" lib key, and the font and
        # control value programs are present.
        ic = InstructionCompiler()
        ic.ufo = quadufo
        ic.otf = TTFont()
        ic.ufo.lib["public.truetype.instructions"] = {
            "formatVersion": "1",
            "controlValueProgram": "PUSHW[]\n511\nSCANCTRL[]",
        }
        ic.setupTable_prep()

        assert "prep" in ic.otf

        # Check if the bytecode is correct, though this may be out of scope
        assert ic.otf["prep"].program.getBytecode() == b"\xb8\x01\xff\x85"
