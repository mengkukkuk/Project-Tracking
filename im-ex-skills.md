## 6. Web Feature Extension: Import/Export (Excel & PDF)

You are an expert Full-Stack Engineer specializing in web-based data processing, file generation, and browser-based extensions. Apply these standards when writing code for importing/exporting Excel and PDF files.

### A. Recommended Tech Stack
- **Excel (Client/Node)**: `exceljs` (Preferred for styling/formatting) or `xlsx` (SheetJS, for lightweight raw data).
- **PDF (Client)**: `jspdf` + `jspdf-autotable` (For tabular data) or `html2pdf.js` (For visual layout matching).
- **PDF (Backend/Node)**: `pdfkit` or `puppeteer` (For pixel-perfect HTML-to-PDF rendering).

---

### B. Technical Standards for Exporting

#### 1. Excel Export Standards
- **Data Streaming**: For large datasets (>10,000 rows), use streaming writers (`exceljs` streaming API) to prevent browser/server memory crashes.
- **Formatting**: Always auto-fit column widths based on cell content length. Format headers with a distinct background color, bold text, and enabled auto-filters.
- **Data Typing**: Explicitly map data types. Ensure dates use ISO format (`YYYY-MM-DD`) or regional Excel date formatting, and financial numbers are typed as `Number` (not `String`) with specific decimal places.

#### 2. PDF Export Standards
- **Layout & Pagination**: Implement auto-pagination. Use `jspdf-autotable` with `didDrawPage` hooks to dynamically inject repeating headers, page numbers ("Page X of Y"), and timestamps.
- **Content Fitting**: Use `styles: { overflow: 'linebreak' }` to prevent long text from clipping. Downscale font sizes automatically if columns exceed page width (A4 Portrait/Landscape optimization).

---

### C. Technical Standards for Importing (Excel/CSV)

#### 1. Security & Validation
- **File Validation**: Always validate the file extension (e.g., `.xlsx`, `.xls`, `.csv`) and Magic Numbers/MIME types on both client and server before processing.
- **Payload Limits**: Enforce maximum file size limits (e.g., max 10MB) to prevent Denial of Service (DoS) via memory exhaustion.
- **Sanitization**: Strip potential formula injection attacks (CSV Injection / Formula Injection). Neutralize cells starting with `=`, `+`, `-`, or `@` by prepending a single quote (`'`).

#### 2. Parsing & Error Handling
- **Header Mapping**: Implement flexible header mapping (case-insensitive, trimming spaces) to match database fields securely.
- **Row-by-Row Validation**: Validate each row against data schemas (e.g., Zod or Joi). Collect all row errors and return a structured summary report to the user instead of throwing a generic crash error.
  ```json
  { "success": false, "errors": [{ "row": 14, "column": "Email", "message": "Invalid email format" }] }
  ```

---

### D. Code Templates & Reference Architecture

#### Template: Client-Side Excel Export (JavaScript / ExcelJS)
```javascript
import ExcelJS from 'exceljs';

async function exportToExcel(data, fileName = 'export.xlsx') {
  const workbook = new ExcelJS.Workbook();
  const worksheet = workbook.addWorksheet('Data Sheet');
  
  // Define columns with explicit widths and formats
  worksheet.columns = Object.keys(data[0] || {}).map(key => ({
    header: key.toUpperCase(),
    key: key,
    width: 20
  }));
  
  // Add Rows
  worksheet.addRows(data);
  
  // Style Header Row
  worksheet.getRow(1).font = { bold: true, color: { argb: 'FFFFFF' } };
  worksheet.getRow(1).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: '4F81BD' } };
  
  // Auto-fit Column Widths dynamically
  worksheet.columns.forEach(column => {
    let maxColumnLength = 0;
    column.eachCell({ includeEmpty: true }, cell => {
      const maxLen = cell.value ? cell.value.toString().length : 0;
      if (maxLen > maxColumnLength) maxColumnLength = maxLen;
    });
    column.width = Math.max(maxColumnLength + 4, 12);
  });

  // Generate and Trigger Download
  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = fileName;
  link.click();
}
```

#### Template: Secure Server-Side File Validation (Node.js)
```javascript
const multer = require('multer');
const path = require('path');

const uploadConfig = multer({
  limits: { fileSize: 10 * 1024 * 1024 }, // 10MB limit
  fileFilter: (req, file, cb) => {
    const allowedExtensions = ['.xlsx', '.xls', '.csv'];
    const ext = path.extname(file.originalname).toLowerCase();
    
    if (allowedExtensions.includes(ext)) {
      return cb(null, true);
    }
    cb(new Error('Invalid file type. Only Excel and CSV files are allowed.'));
  }
});
```
