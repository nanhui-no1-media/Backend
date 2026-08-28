import React, { useState, useEffect, useRef } from "react";
import "../styles/exam-board.css";

interface ScheduleItem {
  id: string;
  subject: string;
  startTime: string;
  endTime: string;
}

const DEFAULT_SCHEDULES: ScheduleItem[] = [
  { id: "1", subject: "语文", startTime: "09:00", endTime: "11:30" },
  { id: "2", subject: "数学", startTime: "15:00", endTime: "17:00" },
];

const SYNC_INTERVAL = 5 * 60 * 1000; // 5分钟同步一次网络时间

export default function ExamBoardPage() {
  // 1. 状态定义
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [currentTime, setCurrentTime] = useState("00:00:00");
  const [currentSubject, setCurrentSubject] = useState("无");
  const [startTime, setStartTime] = useState("--:--");
  const [endTime, setEndTime] = useState("--:--");

  // 从 LocalStorage 读取配置，若没有则用默认数据
  const [schedules, setSchedules] = useState<ScheduleItem[]>(() => {
    const saved = localStorage.getItem("examSchedule");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        return parsed.map((item: any, idx: number) => ({
          ...item,
          id: item.id || `${Date.now()}-${idx}`,
        }));
      } catch (e) {
        console.error("解析本地存储失败:", e);
      }
    }
    return DEFAULT_SCHEDULES;
  });

  // 使用 useRef 保存时间偏移量（毫秒），避免引发不必要的重新渲染
  const timeOffsetRef = useRef<number>(0);

  // 2. 网络授时同步逻辑 (淘宝 API -> 苏宁 API -> 本地时间)
  const syncTime = async () => {
    try {
      const response = await fetch(
        `https://api.m.taobao.com/rest/api3.do?api=mtop.common.gettimestamp&${Date.now()}`
      );
      const data = await response.json();
      if (data && data.data && data.data.t) {
        const serverTimestamp = parseInt(data.data.t, 10);
        timeOffsetRef.current = serverTimestamp - Date.now();
        return;
      }
      throw new Error("数据结构解析失败");
    } catch (error) {
      console.warn("[主接口获取失败，尝试苏宁时间戳备用接口]:", error);
      try {
        const res = await fetch(
          `https://quan.suning.com/getSysTime.do?_=${Date.now()}`
        );
        const suningData = await res.json();
        const tStr = suningData.sysTime1;
        const formatted = `${tStr.slice(0, 4)}-${tStr.slice(4, 6)}-${tStr.slice(
          6,
          8
        )}T${tStr.slice(8, 10)}:${tStr.slice(10, 12)}:${tStr.slice(
          12,
          14
        )}+08:00`;
        const serverTimestamp = new Date(formatted).getTime();
        timeOffsetRef.current = serverTimestamp - Date.now();
      } catch (e) {
        console.warn("[所有授时接口均失败，维持本地系统时间模式]", e);
      }
    }
  };

  // 3. 网络授时定时器
  useEffect(() => {
    syncTime();
    const syncTimer = setInterval(syncTime, SYNC_INTERVAL);
    return () => clearInterval(syncTimer);
  }, []);

  // 4. 实时更新时钟与匹配当前考试
  useEffect(() => {
    const updateDisplay = () => {
      const correctedNow = new Date(Date.now() + timeOffsetRef.current);

      const hours = String(correctedNow.getHours()).padStart(2, "0");
      const minutes = String(correctedNow.getMinutes()).padStart(2, "0");
      const seconds = String(correctedNow.getSeconds()).padStart(2, "0");

      setCurrentTime(`${hours}:${minutes}:${seconds}`);

      // 匹配当前时间是否在某场考试范围内
      const currentHM = `${hours}:${minutes}`;
      let activeExam: ScheduleItem | null = null;

      for (const exam of schedules) {
        if (currentHM >= exam.startTime && currentHM < exam.endTime) {
          activeExam = exam;
          break;
        }
      }

      if (activeExam) {
        setCurrentSubject(activeExam.subject);
        setStartTime(activeExam.startTime);
        setEndTime(activeExam.endTime);
      } else {
        setCurrentSubject("无");
        setStartTime("--:--");
        setEndTime("--:--");
      }
    };

    updateDisplay();
    const timer = setInterval(updateDisplay, 1000);
    return () => clearInterval(timer);
  }, [schedules]);

  // 5. 设置弹窗增删改操作
  const handleAddRow = () => {
    const newItem: ScheduleItem = {
      id: Date.now().toString(),
      subject: "新科目",
      startTime: "09:00",
      endTime: "11:30",
    };
    setSchedules([...schedules, newItem]);
  };

  const handleDeleteRow = (id: string) => {
    setSchedules(schedules.filter((item) => item.id !== id));
  };

  const handleInputChange = (
    id: string,
    field: keyof ScheduleItem,
    value: string
  ) => {
    setSchedules(
      schedules.map((item) =>
        item.id === id ? { ...item, [field]: value } : item
      )
    );
  };

  // 6. 保存配置并持久化到 LocalStorage
  const handleSaveSettings = () => {
    // 过滤空数据并持久化
    const validSchedules = schedules.filter(
      (item) => item.subject && item.startTime && item.endTime
    );
    setSchedules(validSchedules);
    localStorage.setItem("examSchedule", JSON.stringify(validSchedules));
    setIsModalOpen(false);
  };

  return (
    <div className="exam-board-wrapper">
      {/* 右上角齿轮设置按钮 */}
      <button
        id="settings-btn"
        className="settings-btn"
        title="设置"
        onClick={() => setIsModalOpen(true)}
      >
        ⚙️
      </button>

      {/* 设置弹窗面板 */}
      {isModalOpen && (
        <div id="settings-modal" className="modal style-modal-open">
          <div className="modal-content">
            <span
              className="close-btn"
              id="close-modal"
              onClick={() => setIsModalOpen(false)}
            >
              &times;
            </span>
            <h3>考试时间配置列表</h3>
            <table id="schedule-table">
              <thead>
                <tr>
                  <th>科目</th>
                  <th>开始时间</th>
                  <th>结束时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody id="schedule-body">
                {schedules.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <input
                        type="text"
                        className="inp-subject"
                        value={row.subject}
                        placeholder="科目"
                        onChange={(e) =>
                          handleInputChange(row.id, "subject", e.target.value)
                        }
                      />
                    </td>
                    <td>
                      <input
                        type="time"
                        className="inp-start"
                        value={row.startTime}
                        onChange={(e) =>
                          handleInputChange(row.id, "startTime", e.target.value)
                        }
                      />
                    </td>
                    <td>
                      <input
                        type="time"
                        className="inp-end"
                        value={row.endTime}
                        onChange={(e) =>
                          handleInputChange(row.id, "endTime", e.target.value)
                        }
                      />
                    </td>
                    <td>
                      <button
                        className="btn-delete"
                        onClick={() => handleDeleteRow(row.id)}
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button
              id="add-row-btn"
              className="btn-add"
              onClick={handleAddRow}
            >
              + 添加科目
            </button>
            <div className="modal-actions">
              <button
                id="save-settings-btn"
                className="btn-save"
                onClick={handleSaveSettings}
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 页面核心展示区域 */}
      <div className="board-container">
        {/* 第一行：当前时间 */}
        <div className="row1">
          <span id="current-time">{currentTime}</span>
        </div>

        {/* 第二行：当前科目 & 开始时间 */}
        <div className="info-grid">
          <div className="left-col">
            <span>当前科目：</span>
            <span id="current-subject">{currentSubject}</span>
          </div>
          <div className="right-col" id="start-time-container">
            <span>开始时间：</span>
            <span id="start-time">{startTime}</span>
          </div>
        </div>

        {/* 第三行：左侧占位，右侧结束时间 */}
        <div className="info-grid">
          <div className="empty-col"></div>
          <div className="right-col" id="end-time-container">
            <span>结束时间：</span>
            <span id="end-time">{endTime}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
