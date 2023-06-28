# pdf-quick-text
Lightweight package to add text to an existing PDF document.

## Quick example
Here is how you can pump out PDFs from a template file with custom data added.

```python
from pdfquicktext.writer import PDFFactory

with open('names.txt') as fp:
    names = fp.readlines()

with open('template.pdf', 'rb') as fp:
    factory = PDFFactory(fp.read())

for name in names:
    for p in range(factory.get_num_pages()):
        factory.open_page(n)
        # add name at the top of the pages.
        factory.add_text(name, 7.1, 1.03, 10, 'courier')
        factory.close_page()
    factory.save(f'outfiles/{name}.pdf')
    factory.reset()
```
