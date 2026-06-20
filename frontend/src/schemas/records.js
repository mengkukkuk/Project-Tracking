// Schema registry for the per-project auxiliary record types.
//
// Each entry drives both the generic RecordForm (editing) and RecordList
// (compact table) so the six resources share one set of components. Field
// `type` maps to an input: text | textarea | date | number | select | checkbox.
// `columns` selects which fields appear as table columns; `titleKey` is the
// field used as a row's headline. Keys are camelCase to match the API JSON.

export const RECORD_SCHEMAS = {
  ptrack: {
    label: 'Process',
    icon: 'pipelines',
    titleKey: 'process',
    fields: [
      { key: 'process', label: 'Process', type: 'text' },
      { key: 'task', label: 'Task', type: 'textarea' },
      { key: 'pm', label: 'PM', type: 'text' },
      { key: 'startDate', label: 'Start date', type: 'date' },
      { key: 'dueDate', label: 'Due date', type: 'date' },
      { key: 'status', label: 'Status', type: 'text' },
      { key: 'reference', label: 'Reference', type: 'text' },
      { key: 'checked', label: 'Done', type: 'checkbox' },
    ],
    columns: ['process', 'task', 'status', 'dueDate', 'checked'],
  },

  survey: {
    label: 'Survey',
    icon: 'search',
    titleKey: 'department',
    fields: [
      { key: 'date', label: 'Date', type: 'date' },
      { key: 'department', label: 'Department', type: 'text' },
      { key: 'requirement', label: 'Requirement', type: 'textarea' },
      { key: 'issue', label: 'Issue', type: 'textarea' },
      { key: 'limitation', label: 'Limitation', type: 'textarea' },
      { key: 'result', label: 'Result', type: 'textarea' },
      { key: 'conclude', label: 'Conclusion', type: 'textarea' },
      { key: 'surveyor', label: 'Surveyor', type: 'textarea' },
    ],
    columns: ['date', 'department', 'requirement', 'result'],
  },

  mom: {
    label: 'Meeting',
    icon: 'comment',
    titleKey: 'topic',
    fields: [
      { key: 'date', label: 'Date', type: 'date' },
      { key: 'participant', label: 'Participants', type: 'textarea' },
      { key: 'topic', label: 'Topic', type: 'text' },
      { key: 'concerns', label: 'Concerns', type: 'textarea' },
      { key: 'conclude', label: 'Conclusion', type: 'textarea' },
      { key: 'todo', label: 'To-do', type: 'textarea' },
    ],
    columns: ['date', 'topic', 'participant', 'todo'],
  },

  bom: {
    label: 'BOM & Cost',
    icon: 'money',
    titleKey: 'deviceName',
    fields: [
      { key: 'dateApprove', label: 'Approved on', type: 'date' },
      { key: 'category', label: 'Category', type: 'text' },
      { key: 'deviceName', label: 'Device name', type: 'text' },
      { key: 'version', label: 'Version', type: 'text' },
      { key: 'spec', label: 'Spec', type: 'textarea' },
      { key: 'quantity', label: 'Quantity', type: 'number' },
      { key: 'unit', label: 'Unit', type: 'text' },
      { key: 'position', label: 'Position', type: 'text' },
      { key: 'unitPrice', label: 'Unit price', type: 'number' },
      { key: 'totalPrice', label: 'Total price', type: 'number' },
      { key: 'leadTime', label: 'Lead time (days)', type: 'number' },
      { key: 'supplier', label: 'Supplier', type: 'text' },
    ],
    columns: ['deviceName', 'category', 'quantity', 'unitPrice', 'totalPrice'],
  },

  verification: {
    label: 'Verification',
    icon: 'check',
    titleKey: 'testSystem',
    fields: [
      { key: 'date', label: 'Date', type: 'date' },
      { key: 'approver', label: 'Approver', type: 'text' },
      { key: 'testSystem', label: 'Test system', type: 'text' },
      { key: 'testResult', label: 'Test result', type: 'textarea' },
      { key: 'defected', label: 'Defects', type: 'textarea' },
      { key: 'solution', label: 'Solution', type: 'textarea' },
      { key: 'status', label: 'Passed', type: 'checkbox' },
    ],
    columns: ['date', 'testSystem', 'approver', 'status'],
  },

  exceptions: {
    label: 'Exceptions',
    icon: 'alert',
    titleKey: 'informer',
    fields: [
      { key: 'date', label: 'Date', type: 'date' },
      { key: 'informer', label: 'Informer', type: 'text' },
      { key: 'orderList', label: 'Order list', type: 'textarea' },
      { key: 'effectPrice', label: 'Price impact', type: 'textarea' },
      { key: 'effectTech', label: 'Technical impact', type: 'textarea' },
      { key: 'dateNewBom', label: 'New BOM date', type: 'date' },
      { key: 'dateNewPps', label: 'New PPS date', type: 'date' },
    ],
    columns: ['date', 'informer', 'effectPrice', 'effectTech'],
  },
}

// Order of the record tabs as shown in the project detail drawer.
export const RECORD_ORDER = ['ptrack', 'survey', 'mom', 'bom', 'verification', 'exceptions']

export function emptyRecord(resource) {
  const schema = RECORD_SCHEMAS[resource]
  const out = {}
  for (const f of schema.fields) {
    out[f.key] = f.type === 'checkbox' ? false : f.type === 'number' ? null : ''
  }
  return out
}
