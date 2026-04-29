import ReactDiffViewer from 'react-diff-viewer-continued'

interface Props {
  before: Record<string, unknown> | null
  after: Record<string, unknown>
}

export default function DiffViewer({ before, after }: Props) {
  const oldVal = before ? JSON.stringify(before, null, 2) : ''
  const newVal = JSON.stringify(after, null, 2)

  return (
    <div className="text-xs rounded overflow-hidden border border-gray-200">
      <ReactDiffViewer
        oldValue={oldVal}
        newValue={newVal}
        splitView={false}
        hideLineNumbers={false}
        useDarkTheme={false}
      />
    </div>
  )
}
