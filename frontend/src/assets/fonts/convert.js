import fs from 'fs';
import path from 'path';

// Paths - adjust if your TTF is in a different folder
const ttfPath = './THSARABUN.TTF'; 
const outputPath = './THSarabun.js'; // Output module name

try {
  // Read the binary TTF file
  const fontBuffer = fs.readFileSync(ttfPath);
  const base64String = fontBuffer.toString('base64');

  // Format exactly like IBMPlexSansThai.js structure
  const template = `// TH Sarabun (Regular) embedded for jsPDF.
// Generated automatically from original TTF binary.

const FONT_BASE64 =
  "${base64String}";

export function registerThSarabunFont(jsPDFInstance) {
  if (!jsPDFInstance) return;
  
  const fontName = 'THSarabun';
  const fontStyle = 'normal';
  
  jsPDFInstance.addFileToVFS(\`\${fontName}-\${fontStyle}.ttf\`, FONT_BASE64);
  jsPDFInstance.addFont(\`\${fontName}-\${fontStyle}.ttf\`, fontName, fontStyle);
}
`;

  fs.writeFileSync(outputPath, template, 'utf-8');
  console.log(`Successfully converted ${ttfPath} -> ${outputPath}`);
} catch (error) {
  console.error('Failed to convert font:', error);
}