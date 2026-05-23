/**
 * Voice Navigation System - Groq LLM Powered
 * Allows users to navigate the app using voice commands
 */

class VoiceNavigationSystem {
    constructor() {
        this.recognition = null;
        this.synthesis = window.speechSynthesis;
        this.isListening = false;
        this.voiceButton = null;
        this.statusIndicator = null;
        
        this.initializeSpeechRecognition();
        this.createVoiceButton();
    }
    
    initializeSpeechRecognition() {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = false;
            this.recognition.lang = 'en-US';
            
            this.recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                console.log('Voice command:', transcript);
                this.processVoiceCommand(transcript);
            };
            
            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                this.stopListening();
                this.speak('Sorry, I had trouble understanding. Please try again.');
            };
            
            this.recognition.onend = () => {
                this.stopListening();
            };
        } else {
            console.warn('Speech recognition not supported');
        }
    }
    
    createVoiceButton() {
        // Create floating voice button
        const button = document.createElement('button');
        button.id = 'global-voice-nav-button';
        button.className = 'voice-nav-button';
        button.innerHTML = '<i class="fas fa-microphone"></i>';
        button.title = 'Voice Navigation - Click and speak';
        
        // Create status indicator
        const status = document.createElement('div');
        status.id = 'voice-nav-status';
        status.className = 'voice-nav-status';
        status.style.display = 'none';
        
        document.body.appendChild(button);
        document.body.appendChild(status);
        
        this.voiceButton = button;
        this.statusIndicator = status;
        
        button.addEventListener('click', () => {
            if (this.isListening) {
                this.stopListening();
            } else {
                this.startListening();
            }
        });
    }
    
    startListening() {
        if (!this.recognition) {
            this.speak('Voice navigation is not supported in your browser.');
            return;
        }
        
        this.isListening = true;
        this.voiceButton.classList.add('listening');
        this.voiceButton.innerHTML = '<i class="fas fa-stop"></i>';
        
        this.statusIndicator.textContent = 'Listening... Speak your command';
        this.statusIndicator.style.display = 'block';
        
        this.recognition.start();
        this.speak('I\'m listening. Where would you like to go?');
    }
    
    stopListening() {
        this.isListening = false;
        this.voiceButton.classList.remove('listening');
        this.voiceButton.innerHTML = '<i class="fas fa-microphone"></i>';
        
        this.statusIndicator.style.display = 'none';
        
        if (this.recognition) {
            this.recognition.stop();
        }
    }
    
    async processVoiceCommand(command) {
        this.statusIndicator.textContent = 'Processing...';
        
        try {
            // Send command to Groq LLM for intelligent processing
            const response = await fetch('/process_voice_navigation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ command: command })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.speak(data.message);
                
                // Navigate after speaking
                if (data.url) {
                    setTimeout(() => {
                        window.location.href = data.url;
                    }, 1500);
                }
            } else {
                this.speak(data.message || 'Sorry, I didn\'t understand that command.');
            }
        } catch (error) {
            console.error('Error processing voice command:', error);
            this.speak('Sorry, there was an error processing your command.');
        }
    }
    
    speak(text) {
        // Cancel any ongoing speech
        this.synthesis.cancel();
        
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.9;
        utterance.pitch = 1;
        utterance.volume = 1;
        
        this.synthesis.speak(utterance);
    }
}

// Initialize voice navigation when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if user is logged in and NOT on the ai_assistant page
    const isAiAssistantPage = window.location.pathname.includes('/ai_assistant');
    if (document.body.dataset.userLoggedIn === 'true' && !isAiAssistantPage) {
        window.voiceNav = new VoiceNavigationSystem();
        console.log('✅ Voice Navigation System initialized');
    }
});

// Made with Bob
