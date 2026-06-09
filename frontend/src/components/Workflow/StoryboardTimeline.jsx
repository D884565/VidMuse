export default function StoryboardTimeline({ frames = [], selectedFrameId = null, onSelectFrame }) {
  return (
    <div className="storyboard-timeline">
      {frames.map((frame) => (
        <button
          key={frame.id}
          type="button"
          className={`timeline-frame ${frame.dirty ? 'is-dirty' : ''} ${frame.status === 3 ? 'is-failed' : ''} ${frame.id === selectedFrameId ? 'is-active' : ''}`}
          onClick={() => onSelectFrame?.(frame)}
        >
          <span>#{frame.sequence}</span>
          <span>{Math.round(Number(frame.duration || 0))}s</span>
          <span>{frame.status}</span>
          {frame.dirty ? <span>待合成</span> : null}
        </button>
      ))}
    </div>
  )
}
