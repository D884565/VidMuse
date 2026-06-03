import { useState } from 'react'
import { ChevronDown, ChevronRight, User, Bot, Wrench, ArrowRight, CheckCircle, XCircle } from 'lucide-react'

/**
 * 推理轨迹时间线组件
 * @param {Object} trace 完整的轨迹详情数据
 */
export default function TraceTimeline({ trace }) {
  const [expandedSections, setExpandedSections] = useState({
    user_input: true,
    system_prompt: false,
    reasoning: true,
    tool_calls: true,
    final_answer: true,
    messages_history: false
  })

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }

  const renderJSON = (data) => {
    if (!data) return '无数据'
    try {
      return JSON.stringify(data, null, 2)
    } catch (e) {
      return String(data)
    }
  }

  return (
    <div className="space-y-4">
      {/* 用户输入 */}
      <div className="bg-[var(--bg-sidebar)] rounded-xl border border-[var(--border-soft)] overflow-hidden">
        <button
          onClick={() => toggleSection('user_input')}
          className="w-full flex items-center justify-between p-4 hover:bg-[var(--bg)] transition-colors"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 rounded-lg text-blue-500">
              <User size={18} />
            </div>
            <span className="font-medium">用户输入</span>
          </div>
          {expandedSections.user_input ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        </button>
        {expandedSections.user_input && (
          <div className="p-4 border-t border-[var(--border-soft)]">
            <p className="whitespace-pre-wrap">{trace.user_input}</p>
          </div>
        )}
      </div>

      {/* 系统提示词 */}
      <div className="bg-[var(--bg-sidebar)] rounded-xl border border-[var(--border-soft)] overflow-hidden">
        <button
          onClick={() => toggleSection('system_prompt')}
          className="w-full flex items-center justify-between p-4 hover:bg-[var(--bg)] transition-colors"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/10 rounded-lg text-purple-500">
              <Bot size={18} />
            </div>
            <span className="font-medium">系统提示词</span>
          </div>
          {expandedSections.system_prompt ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        </button>
        {expandedSections.system_prompt && (
          <div className="p-4 border-t border-[var(--border-soft)]">
            <p className="whitespace-pre-wrap text-sm">{trace.system_prompt}</p>
          </div>
        )}
      </div>

      {/* 推理过程 */}
      <div className="bg-[var(--bg-sidebar)] rounded-xl border border-[var(--border-soft)] overflow-hidden">
        <button
          onClick={() => toggleSection('reasoning')}
          className="w-full flex items-center justify-between p-4 hover:bg-[var(--bg)] transition-colors"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-500/10 rounded-lg text-yellow-500">
              <Bot size={18} />
            </div>
            <span className="font-medium">推理过程 ({trace.iterations} 轮迭代)</span>
          </div>
          {expandedSections.reasoning ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        </button>
        {expandedSections.reasoning && (
          <div className="p-4 border-t border-[var(--border-soft)]">
            <div className="space-y-4">
              {/* 工具调用链 */}
              {trace.tool_calls?.length > 0 && trace.tool_calls.map((call, index) => (
                <div key={index} className="ml-6 border-l-2 border-[var(--border-soft)] pl-4 pb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Wrench size={14} className="text-orange-500" />
                    <span className="text-sm font-medium">工具调用 #{index + 1}</span>
                  </div>
                  <div className="bg-[var(--bg)] rounded-lg p-3 mb-2">
                    <pre className="text-xs overflow-x-auto">{renderJSON(call)}</pre>
                  </div>
                  {trace.tool_results?.[index] && (
                    <>
                      <div className="flex items-center gap-2 mb-2">
                        <ArrowRight size={14} className="text-green-500" />
                        <span className="text-sm font-medium">返回结果</span>
                      </div>
                      <div className="bg-[var(--bg)] rounded-lg p-3">
                        <pre className="text-xs overflow-x-auto">{renderJSON(trace.tool_results[index])}</pre>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 最终回答 */}
      <div className="bg-[var(--bg-sidebar)] rounded-xl border border-[var(--border-soft)] overflow-hidden">
        <button
          onClick={() => toggleSection('final_answer')}
          className="w-full flex items-center justify-between p-4 hover:bg-[var(--bg)] transition-colors"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/10 rounded-lg text-green-500">
              {trace.success ? <CheckCircle size={18} /> : <XCircle size={18} />}
            </div>
            <span className="font-medium">最终回答</span>
          </div>
          {expandedSections.final_answer ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        </button>
        {expandedSections.final_answer && (
          <div className="p-4 border-t border-[var(--border-soft)]">
            {trace.success ? (
              <p className="whitespace-pre-wrap">{trace.final_answer || '无返回结果'}</p>
            ) : (
              <div className="text-red-500">
                <p className="font-medium mb-2">执行失败</p>
                <p className="whitespace-pre-wrap">{trace.error_msg}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 完整消息历史 */}
      <div className="bg-[var(--bg-sidebar)] rounded-xl border border-[var(--border-soft)] overflow-hidden">
        <button
          onClick={() => toggleSection('messages_history')}
          className="w-full flex items-center justify-between p-4 hover:bg-[var(--bg)] transition-colors"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gray-500/10 rounded-lg text-gray-500">
              <Bot size={18} />
            </div>
            <span className="font-medium">完整消息历史 ({trace.messages_history?.length || 0} 条)</span>
          </div>
          {expandedSections.messages_history ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        </button>
        {expandedSections.messages_history && (
          <div className="p-4 border-t border-[var(--border-soft)]">
            <pre className="text-xs overflow-x-auto bg-[var(--bg)] rounded-lg p-3">
              {renderJSON(trace.messages_history)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
