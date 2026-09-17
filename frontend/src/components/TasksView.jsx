import { useEffect, useState } from "react";
import { api } from "../api";

const STATUS_TABS = [
  { key: "open", label: "Open" },
  { key: "done", label: "Done" },
];

export default function TasksView({ onError }) {
  const [status, setStatus] = useState("open");
  const [tasks, setTasks] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const [taskList, notifList] = await Promise.all([
        api.listTasks({ status }),
        api.listNotifications(),
      ]);
      setTasks(taskList);
      setNotifications(notifList);
    } catch (e) {
      onError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  async function handleComplete(id) {
    try {
      await api.completeTask(id);
      await refresh();
    } catch (e) {
      onError(e.message);
    }
  }

  return (
    <div className="tasks-view">
      <div className="tasks-main">
        <div className="doc-list-tabs">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.key}
              className={tab.key === status ? "tab active" : "tab"}
              onClick={() => setStatus(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {loading && <p className="muted">Loading...</p>}
        {!loading && tasks.length === 0 && <p className="muted">No {status} tasks.</p>}

        <table className="tasks-table">
          <thead>
            <tr>
              <th>Task</th>
              <th>Document</th>
              <th>Owner</th>
              <th>Deadline</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id}>
                <td>{t.text}</td>
                <td className="muted">{t.document_filename}</td>
                <td>{t.owner || "unassigned"}</td>
                <td>{t.deadline || "—"}</td>
                <td>
                  {t.status === "open" ? (
                    <button className="link-button" onClick={() => handleComplete(t.id)}>
                      Mark done
                    </button>
                  ) : (
                    <span className="muted">✓ done</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="notifications-feed">
        <h3>Recent notifications</h3>
        {notifications.length === 0 && <p className="muted">Nothing yet.</p>}
        <ul>
          {notifications.map((n) => (
            <li key={n.id} className={n.delivered ? "" : "notif-failed"}>
              <div className="notif-header">
                <strong>{n.recipient}</strong>
                <span className="badge">{n.channel}</span>
                {!n.delivered && <span className="badge status-rejected">failed</span>}
              </div>
              <div className="notif-message">{n.message}</div>
              <div className="muted notif-time">{new Date(n.created_at).toLocaleString()}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
