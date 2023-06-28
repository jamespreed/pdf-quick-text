from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Union, List, Tuple
import pikepdf


class BaseFont(Enum):
    courier = '/Courier'
    courierbold = '/Courier-Bold'
    courierboldoblique = '/Courier-BoldOblique'
    courieroblique = '/Courier-Oblique'
    helvetica = '/Helvetica'
    helveticabold = '/Helvetica-Bold'
    helveticaboldoblique = '/Helvetica-BoldOblique'
    helveticaoblique = '/Helvetica-Oblique'
    timesroman = '/Times-Roman'
    timesbold = '/Times-Bold'
    timesitalic = '/Times-Italic'
    timesbolditalic = '/Times-BoldItalic'
    symbol = '/Symbol'
    zapfdingbats = '/ZapfDingbats'


class PDFQuickTextError(Exception):
    pass


class PDFFactory:
    DPI = 72

    def __init__(self, pdf_bytes: bytes) -> None:
        self.pdf_bytes = pdf_bytes
        self.pdf_object = pikepdf.open(BytesIO(self.pdf_path))
        self.page_object = None
        self._current_page = None
        self._page_instructions = None

    @property
    def current_page(self) -> int:
        return self._current_page

    def _add_font(self, font: Union[str, BaseFont]) -> pikepdf.Name:
        """
        Adds a font to the current page resources.
        """
        self._assert_page_is_open()
        if isinstance(font, str):
            try:
                font = BaseFont[font]
            except KeyError:
                raise KeyError(f'{font!r} is not a BaseFont enum key')
        
        pdf_font = pikepdf.Name(font.value)
        if pdf_font in self.page_object.resources.Font:
            return
        
        font_dict = pikepdf.Dictionary(
            Type = pikepdf.Name.Font,
            Subtype = pikepdf.Name.Type1,
            BaseFont = pdf_font,
        )

        self.pdf_object.make_indirect(font_dict)
        self.page_object.add_resource(font_dict, pikepdf.Name.Font, font.value)
        return pdf_font

    def _open_page(self, page_ix: int) -> None:
        """
        Loads the instructions for a page of the PDF.  Pages numbers are 
        zero-indexed.
        """
        # for now do 1 page at a time; later i will add support for multiple
        # page streams.
        if self.current_page is not None:
            raise PDFQuickTextError(
                'A page is already open and must be closed prior to opening a new page.'
            )
        
        self._current_page = page_ix
        self.page_object = self.pdf_object.pages[page_ix]
        self._page_instructions = pikepdf.parse_content_stream(self.page_object)

    def _close_page(self) -> None:
        """
        Closes the currently opened page of the PDF.
        """
        self._assert_page_is_open()
        content_stream = pikepdf.unparse_content_stream(self._page_instructions)
        self.page_object.Contents = content_stream
        self._current_page = None
        self._page_instructions = None
        self.page_object = None

    def _assert_page_is_open(self):
        """
        Raises an exception if a page is not open.
        """
        if self.page_object is None:
            raise PDFQuickTextError('A page must be opened prior to this operation.')

    def _make_text_instructions(self,
                                text: str,
                                x: float,
                                y: float,
                                size: float,
                                font: Union[str, BaseFont],
                                ) -> List[pikepdf.ContentStreamInstruction]:
        """
        Creates the instuction set to place `text` as the location `x`, `y`
        using `font` of the size `size`.
        """
        CSI = pikepdf.ContentStreamInstruction
        pdf_font = self._add_font(font)

        instructions = [
            CSI([], pikepdf.Operator('BT')),
            CSI([pdf_font, size], pikepdf.Operator('Tf')),
            CSI([1, 0, 0, 1, x, y], pikepdf.Operator('Tm')),
            CSI([pikepdf.String(text)], pikepdf.Operator('Tj')),
            CSI([], pikepdf.Operator('ET')),
        ]

        return instructions
    
    def _insert_new_instructions(self, new: List[pikepdf.ContentStreamInstruction]) -> None:
        """
        Inserts the new instructions into the current page's instruction set
        after the last ENDTEXT command.
        """
        insert_index = 0
        for i, (_, op) in enumerate(self._page_instructions):
            if str(op) == 'ET':
                insert_index = i
        self._page_instructions = [
            *self._page_instructions[:insert_index],
            *new,
            *self._page_instructions[insert_index:],
        ]

    def _add_text_xy_points(self,
                            text: str,
                            x: float,
                            y: float,
                            size: float,
                            font: Union[str, BaseFont],
                            ) -> None:
        """
        Add text the open page of the PDF at the location (x, y).  The text
        coordinates are measured in points from the bottom left corner of 
        the page.
        """
        instructions = self._make_text_instructions(text, x, y, size, font)
        self._insert_new_instructions(instructions)

    def add_text(self,
                 text: str,
                 inches_from_left: float,
                 inches_from_top: float,
                 size: float = 11.0,
                 font: Union[str, BaseFont] = 'timesroman',
                 ) -> None:
        """
        Adds text to the current page located at `inches_from_left` from the 
        left edge and `inches_from_top` from the top edge.  The text `size` is
        in points and rendered using `font` typeface.
        """
        _, _, _, y_top = self.get_page_dimension()
        x = self.DPI * inches_from_left
        y = y_top - self.DPI * inches_from_top
        self._add_text_xy_points(text, x, y, size, font)

    def add_text_cm(self,
                    text: str,
                    cm_from_left: float,
                    cm_from_top: float,
                    size: float = 11.0,
                    font: Union[str, BaseFont] = 'timesroman',
                    ) -> None:
        """
        Adds text to the current page located at `cm_from_left` centimeters 
        from the left edge and `cm_from_top` centimeters from the top edge.  
        The text `size` is in points and rendered using `font` typeface.
        """
        inches_from_left = 2.54 * cm_from_left
        inches_from_top = 2.54 * cm_from_top
        self.add_text(text, inches_from_left, inches_from_top, size, font)

    def get_page_dimension(self) -> Tuple[int]:
        """
        Returns the open page's dimensions in points as 
        (x_left, y_bottom, x_right, y_top)
        """
        self._assert_page_is_open()

        if '/MediaBox' in self.page_object:
            return tuple(self.page_object.MediaBox)
        # fall back to ANSI A (US Letter) 
        return (0, 0, 612, 792)
