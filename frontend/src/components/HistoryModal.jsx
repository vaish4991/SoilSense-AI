import './HistoryModal.css';

export default function HistoryModal({ isOpen, onClose, history, onSelect, onClear }) {
  if (!isOpen) return null;

  const handleExportJSON = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(history, null, 2));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', dataStr);
    dlAnchor.setAttribute('download', `soilsense_history_${new Date().toISOString().slice(0, 10)}.json`);
    dlAnchor.click();
  };

  return (
    <div className="history-modal-backdrop" onClick={onClose}>
      <div className="history-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="history-header">
          <div className="history-title">
            <span>📚</span>
            <span>Soil Dossier History</span>
            <span className="badge badge-amber" style={{ fontSize: 10, padding: '2px 8px' }}>
              {history.length} Saved
            </span>
          </div>
          <button type="button" className="history-close-btn" onClick={onClose} aria-label="Close drawer">
            ✕
          </button>
        </div>

        <div className="history-content">
          {history.length === 0 ? (
            <div className="history-empty">
              <span style={{ fontSize: 36 }}>🌱</span>
              <p>No past analyses saved yet.</p>
              <span style={{ fontSize: 12 }}>Run an autonomous soil analysis to save telemetry here.</span>
            </div>
          ) : (
            history.map((item, idx) => (
              <div
                key={item.id || idx}
                className="history-item"
                onClick={() => {
                  onSelect(item.data);
                  onClose();
                }}
              >
                <div className="history-item-top">
                  <span className="history-item-ph">
                    pH {item.data?.ph_estimate?.ph_value?.toFixed(2) ?? '—'}
                  </span>
                  <span className="history-item-date">
                    {new Date(item.timestamp).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
                <div className="history-item-desc">
                  {item.description || 'Soil Profile Record'}
                </div>
                <div className="history-item-footer">
                  <span>📍 {item.location || 'Generic Field'}</span>
                  <span>🌾 {item.targetCrop || 'Multi-crop'}</span>
                  <span className="badge badge-green" style={{ fontSize: 9, padding: '1px 6px' }}>
                    {Math.round((item.data?.ph_estimate?.confidence ?? 0.8) * 100)}% Conf
                  </span>
                </div>
              </div>
            ))
          )}
        </div>

        {history.length > 0 && (
          <div className="history-actions">
            <button type="button" className="history-btn" onClick={handleExportJSON}>
              📥 Export JSON
            </button>
            <button
              type="button"
              className="history-btn"
              onClick={onClear}
              style={{ color: '#fca5a5', borderColor: 'rgba(239, 68, 68, 0.3)' }}
            >
              🗑️ Clear
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
