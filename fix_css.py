import re

with open('static/css/style.css', 'r') as f:
    content = f.read()

start_marker = "/* AI Assistant */"
end_marker = "/* Mobile optimizations */"

new_css = """/* AI Assistant */
.chat-container {
    height: 400px;
    overflow-y: auto;
    padding: 16px;
    background-color: var(--light-color);
    border-radius: 20px;
    margin-bottom: 20px;
    -webkit-overflow-scrolling: touch;
    border: 1px solid rgba(0,0,0,0.05);
}

.chat-message {
    max-width: 85%;
    padding: 12px 18px;
    border-radius: 20px;
    margin-bottom: 12px;
    position: relative;
    word-wrap: break-word;
    line-height: 1.5;
    font-size: 0.95rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.user-message {
    background-color: var(--primary-color);
    color: white;
    margin-left: auto;
    border-bottom-right-radius: 4px;
}

.assistant-message {
    background-color: white;
    color: #333;
    margin-right: auto;
    border-bottom-left-radius: 4px;
}

/* ============================================
   AI ASSISTANT - MOBILE APP LAYOUT
   ============================================ */

.ai-assistant-container {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 60px);
    max-height: calc(100vh - 60px);
    overflow: hidden;
    padding: 0;
    margin: 0 -12px;
    background-color: var(--light-color);
}

.ai-header {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    padding: 16px 20px;
    background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-color-dark) 100%);
    color: white;
    box-shadow: var(--shadow-sm);
    z-index: 10;
}

.ai-header .back-button {
    color: white;
    font-size: 1.5rem;
    margin-right: 16px;
    text-decoration: none;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    transition: background-color 0.2s ease;
}

.ai-header .back-button:active {
    background-color: rgba(255,255,255,0.2);
}

.ai-header h1 {
    font-size: 1.3rem;
    font-weight: 600;
    margin: 0;
    color: white;
}

.ai-assistant-container .chat-container {
    flex: 1 1 auto;
    overflow-y: auto;
    padding: 20px 16px;
    background-color: var(--light-color);
    -webkit-overflow-scrolling: touch;
    margin: 0;
    border-radius: 0;
    border: none;
}

.quick-questions-container {
    flex: 0 0 auto;
    padding: 12px 16px;
    background-color: var(--light-color);
    display: flex;
    gap: 8px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
}

.quick-questions-container::-webkit-scrollbar {
    display: none;
}

.quick-questions-container .quick-question {
    flex: 0 0 auto;
    white-space: nowrap;
    padding: 10px 16px;
    background-color: white;
    border: 1px solid rgba(0,0,0,0.1);
    color: var(--primary-color);
    border-radius: 20px;
    font-size: 0.9rem;
    font-weight: 500;
    transition: all 0.2s ease;
    box-shadow: var(--shadow-sm);
}

.quick-questions-container .quick-question:active {
    transform: scale(0.96);
    background-color: var(--primary-color);
    color: white;
}

.chat-input-fixed {
    flex: 0 0 auto;
    padding: 12px 16px;
    padding-bottom: calc(16px + env(safe-area-inset-bottom));
    background-color: white;
    border-top: 1px solid rgba(0,0,0,0.05);
    box-shadow: 0 -4px 12px rgba(0,0,0,0.03);
    z-index: 10;
}

.chat-input-fixed .d-flex {
    width: 100%;
    gap: 12px;
    align-items: flex-end;
}

.chat-input-fixed input {
    flex: 1 1 auto;
    border-radius: 24px;
    padding: 14px 20px;
    border: 1px solid #e0e0e0;
    background-color: #f9f9f9;
    font-size: 16px;
    transition: all 0.2s ease;
    min-width: 0;
}

.chat-input-fixed input:focus {
    border-color: var(--primary-color);
    background-color: white;
    outline: none;
    box-shadow: 0 0 0 3px rgba(78, 122, 220, 0.1);
}

.chat-input-fixed button,
.voice-input-button {
    flex: 0 0 auto;
    border-radius: 50%;
    width: 50px;
    height: 50px;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    border: none;
    transition: all 0.2s ease;
    background-color: var(--primary-color);
    color: white;
    box-shadow: 0 4px 10px rgba(78, 122, 220, 0.3);
}

.chat-input-fixed button:active,
.voice-input-button:active {
    transform: scale(0.92);
}

/* ============================================
   VOICE INPUT STATUS
   ============================================ */
.voice-input-button.listening {
    background: var(--danger-color);
    animation: pulse-voice 1.5s infinite;
    box-shadow: 0 4px 16px rgba(239, 68, 68, 0.4);
}

@keyframes pulse-voice {
    0%, 100% {
        transform: scale(1);
        box-shadow: 0 4px 16px rgba(239, 68, 68, 0.4);
    }
    50% {
        transform: scale(1.1);
        box-shadow: 0 6px 24px rgba(239, 68, 68, 0.6);
    }
}

.voice-status-indicator {
    position: fixed;
    bottom: calc(100px + env(safe-area-inset-bottom));
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 0, 0, 0.85);
    color: white;
    padding: 12px 24px;
    border-radius: 30px;
    font-size: 0.9rem;
    font-weight: 600;
    z-index: 999;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    animation: slideUp 0.3s ease;
    display: none;
    backdrop-filter: blur(4px);
}

.voice-status-indicator.show {
    display: block;
}

@media (max-width: 767px) {
    .ai-assistant-container {
        height: 100vh;
        max-height: 100vh;
        margin: 0;
    }
    
    .ai-header {
        padding: 14px 16px;
        padding-top: calc(14px + env(safe-area-inset-top));
    }
    
    .ai-header h1 {
        font-size: 1.2rem;
    }
    
    .ai-header .back-button {
        width: 36px;
        height: 36px;
        font-size: 1.3rem;
        margin-right: 12px;
    }
    
    .quick-questions-container {
        padding: 10px 12px;
        gap: 8px;
    }
    
    .chat-input-fixed {
        padding: 10px 12px;
        padding-bottom: calc(12px + env(safe-area-inset-bottom));
    }
    
    .chat-input-fixed input {
        padding: 12px 18px;
        font-size: 16px;
    }
    
    .chat-input-fixed button,
    .voice-input-button {
        width: 48px;
        height: 48px;
        font-size: 1.15rem;
    }
}

@media (min-width: 768px) {
    .ai-assistant-container {
        max-width: 800px;
        margin: 0 auto;
        border-radius: 20px;
        overflow: hidden;
        box-shadow: var(--shadow-lg);
    }
}

"""

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + new_css + content[end_idx:]
    with open('static/css/style.css', 'w') as f:
        f.write(new_content)
    print("CSS updated successfully.")
else:
    print("Markers not found.")
