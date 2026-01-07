/**
 * Brain Map Visualization for OptoGrid Dashboard
 * Renders the brain map with LED positions and handles LED selection
 */
class BrainMapVisualization {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.ledPositions = [];
        this.ledSelectionValue = 0n; // Use BigInt for uint64_t compatibility
        this.ledCheckMask = (1n << 64n) - 1n; // All intact by default (using BigInt for 64-bit)
        
        // LED dimensions
        this.ledWidth = 12;
        this.ledHeight = 23
        
        this.setupCanvas();
        this.calculateLedPositions();
        this.setupEventListeners();
        this.draw();
    }
    
    setupCanvas() {
        // Set up high DPI canvas
        const rect = this.canvas.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        
        this.canvas.width = 358 * dpr;
        this.canvas.height = 300 * dpr;
        
        this.ctx.scale(dpr, dpr);
        this.canvas.style.width = 358 + 'px';
        this.canvas.style.height = 300 + 'px';
        
        this.canvasWidth = 358;
        this.canvasHeight = 300;
    }
    
    calculateLedPositions() {
        // LED positioning parameters - scale based on canvas size
        const scaleX = this.canvasWidth / 358;
        const scaleY = this.canvasHeight / 300;
        
        const xSpace = Math.floor(14 * scaleX);
        const ySpace = Math.floor(40 * scaleY);
        const centerX = Math.floor(172 * scaleX);
        const centerY = Math.floor(10 * scaleY)-1;
        
        // LED pixel coordinates mapping (based on the Qt version)
        const ledPixelMap = {
            // Row 1 (bits 0-7)
            0: [centerX - 11*xSpace + Math.floor(14*scaleX)+4, centerY + 5*ySpace],
            1: [centerX - 5*xSpace + Math.floor(2*scaleX)+3, centerY],
            2: [centerX - 3*xSpace + Math.floor(1*scaleX)+2, centerY],
            3: [centerX - 1*xSpace+1, centerY],
            4: [centerX + 1*xSpace, centerY],
            5: [centerX + 3*xSpace - Math.floor(1*scaleX)-1, centerY],
            6: [centerX + 5*xSpace - Math.floor(2*scaleX)-2, centerY],
            7: [centerX + 11*xSpace - Math.floor(14*scaleX)-3, centerY + 5*ySpace],

            // Row 2 (bits 8-15)
            8: [centerX - 7*xSpace + Math.floor(5*scaleX)+4, centerY + 1*ySpace],
            9: [centerX - 5*xSpace + Math.floor(2*scaleX)+3, centerY + 1*ySpace],
            10: [centerX - 3*xSpace + Math.floor(1*scaleX)+2, centerY + 1*ySpace],
            11: [centerX - 1*xSpace+1, centerY + 1*ySpace],
            12: [centerX + 1*xSpace, centerY + 1*ySpace],
            13: [centerX + 3*xSpace - Math.floor(1*scaleX)-1, centerY + 1*ySpace],
            14: [centerX + 5*xSpace - Math.floor(2*scaleX)-2, centerY + 1*ySpace],
            15: [centerX + 7*xSpace - Math.floor(5*scaleX)-3, centerY + 1*ySpace],

            // Row 3 (bits 16-23)
            16: [centerX - 7*xSpace + Math.floor(5*scaleX)+4, centerY + 2*ySpace],
            17: [centerX - 5*xSpace + Math.floor(2*scaleX)+3, centerY + 2*ySpace],
            18: [centerX - 3*xSpace + Math.floor(1*scaleX)+2, centerY + 2*ySpace],
            19: [centerX - 1*xSpace+1, centerY + 2*ySpace],
            20: [centerX + 1*xSpace, centerY + 2*ySpace],
            21: [centerX + 3*xSpace - Math.floor(1*scaleX)-1, centerY + 2*ySpace],
            22: [centerX + 5*xSpace - Math.floor(2*scaleX)-2, centerY + 2*ySpace],
            23: [centerX + 7*xSpace - Math.floor(5*scaleX)-3, centerY + 2*ySpace],

            // Row 4 (bits 24-31)
            24: [centerX - 7*xSpace + Math.floor(5*scaleX)+4, centerY + 3*ySpace],
            25: [centerX - 5*xSpace + Math.floor(2*scaleX)+3, centerY + 3*ySpace],
            26: [centerX - 3*xSpace + Math.floor(1*scaleX)+2, centerY + 3*ySpace],
            27: [centerX - 1*xSpace+1, centerY + 3*ySpace],
            28: [centerX + 1*xSpace, centerY + 3*ySpace],
            29: [centerX + 3*xSpace - Math.floor(1*scaleX)-1, centerY + 3*ySpace],
            30: [centerX + 5*xSpace - Math.floor(2*scaleX)-2, centerY + 3*ySpace],
            31: [centerX + 7*xSpace - Math.floor(5*scaleX)-3, centerY + 3*ySpace],

            // Row 5 (bits 32-39)
            32: [centerX - 7*xSpace + Math.floor(5*scaleX)+4, centerY + 4*ySpace],
            33: [centerX - 5*xSpace + Math.floor(2*scaleX)+3, centerY + 4*ySpace],
            34: [centerX - 3*xSpace + Math.floor(1*scaleX)+2, centerY + 4*ySpace],
            35: [centerX - 1*xSpace+1, centerY + 4*ySpace],
            36: [centerX + 1*xSpace, centerY + 4*ySpace],
            37: [centerX + 3*xSpace - Math.floor(1*scaleX)-1, centerY + 4*ySpace],
            38: [centerX + 5*xSpace - Math.floor(2*scaleX)-2, centerY + 4*ySpace],
            39: [centerX + 7*xSpace - Math.floor(5*scaleX)-3, centerY + 4*ySpace],

            // Row 6 (bits 40-47)
            40: [centerX - 7*xSpace + Math.floor(5*scaleX)+4, centerY + 5*ySpace],
            41: [centerX - 5*xSpace + Math.floor(2*scaleX)+3, centerY + 5*ySpace],
            42: [centerX - 3*xSpace + Math.floor(1*scaleX)+2, centerY + 5*ySpace],
            43: [centerX - 1*xSpace+1, centerY + 5*ySpace],
            44: [centerX + 1*xSpace, centerY + 5*ySpace],
            45: [centerX + 3*xSpace - Math.floor(1*scaleX)-1, centerY + 5*ySpace],
            46: [centerX + 5*xSpace - Math.floor(2*scaleX)-2, centerY + 5*ySpace],
            47: [centerX + 7*xSpace - Math.floor(5*scaleX)-3, centerY + 5*ySpace],

            // Row 7 (bits 48-55)
            48: [centerX - 7*xSpace + Math.floor(5*scaleX)+4, centerY + 6*ySpace],
            49: [centerX - 5*xSpace + Math.floor(2*scaleX)+3, centerY + 6*ySpace],
            50: [centerX - 3*xSpace + Math.floor(1*scaleX)+2, centerY + 6*ySpace],
            51: [centerX - 1*xSpace+1, centerY + 6*ySpace],
            52: [centerX + 1*xSpace, centerY + 6*ySpace],
            53: [centerX + 3*xSpace - Math.floor(1*scaleX)-1, centerY + 6*ySpace],
            54: [centerX + 5*xSpace - Math.floor(2*scaleX)-2, centerY + 6*ySpace],
            55: [centerX + 7*xSpace - Math.floor(5*scaleX)-3, centerY + 6*ySpace],

            // Row 8 (bits 56-63)
            56: [centerX - 9*xSpace + Math.floor(8*scaleX)+4, centerY + 6*ySpace],
            57: [centerX - 9*xSpace + Math.floor(8*scaleX)+4, centerY + 5*ySpace],
            58: [centerX - 9*xSpace + Math.floor(8*scaleX)+4, centerY + 4*ySpace],
            59: [centerX - 9*xSpace + Math.floor(8*scaleX)+4, centerY + 3*ySpace],
            60: [centerX + 9*xSpace - Math.floor(8*scaleX)-3, centerY + 3*ySpace],
            61: [centerX + 9*xSpace - Math.floor(8*scaleX)-3, centerY + 4*ySpace],
            62: [centerX + 9*xSpace - Math.floor(8*scaleX)-3, centerY + 5*ySpace],
            63: [centerX + 9*xSpace - Math.floor(8*scaleX)-3, centerY + 6*ySpace],
        };

        // Create LED position objects
        this.ledPositions = [];
        for (let bitPosition = 0; bitPosition < 64; bitPosition++) {
            if (bitPosition in ledPixelMap) {
                const [x, y] = ledPixelMap[bitPosition];
                const ledPos = {
                    x: x,
                    y: y,
                    bit: bitPosition,
                    coords: [x, y, x + this.ledWidth, y + this.ledHeight],
                    gridX: (bitPosition % 8) + 1,
                    gridY: Math.floor(bitPosition / 8) + 1
                };
                this.ledPositions.push(ledPos);
            }
        }
    }
    
    setupEventListeners() {
        this.canvas.addEventListener('click', (event) => {
            const rect = this.canvas.getBoundingClientRect();
            const x = event.clientX - rect.left;
            const y = event.clientY - rect.top;
            
            // Find clicked LED
            for (const ledPos of this.ledPositions) {
                const [x1, y1, x2, y2] = ledPos.coords;
                if (x >= x1 && x <= x2 && y >= y1 && y <= y2) {
                    this.onLedClicked(ledPos.bit);
                    break;
                }
            }
        });
        
        // Add cursor pointer when hovering over LEDs
        this.canvas.addEventListener('mousemove', (event) => {
            const rect = this.canvas.getBoundingClientRect();
            const x = event.clientX - rect.left;
            const y = event.clientY - rect.top;
            
            let overLed = false;
            for (const ledPos of this.ledPositions) {
                const [x1, y1, x2, y2] = ledPos.coords;
                if (x >= x1 && x <= x2 && y >= y1 && y <= y2) {
                    overLed = true;
                    break;
                }
            }
            
            this.canvas.style.cursor = overLed ? 'pointer' : 'default';
        });
    }
    
    onLedClicked(bitPosition) {
        // Toggle LED selection using BigInt for proper 64-bit handling
        this.ledSelectionValue ^= (1n << BigInt(bitPosition));
        this.draw();
        
        // Notify the main app
        if (window.optoGridApp) {
            window.optoGridApp.onLedClicked(bitPosition);
        }
    }
    
    updateLedSelection(value) {
        this.ledSelectionValue = BigInt(value);
        this.draw();
    }
    
    updateLedCheckOverlay(ledCheckMask) {
        // Convert input to BigInt for proper uint64_t handling
        this.ledCheckMask = BigInt(ledCheckMask);
        this.draw();
    }
    
    draw() {
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvasWidth, this.canvasHeight);
        
        // Draw brain map background (placeholder for now)
        this.loadBrainMapImage('brainmap.png');
        this.drawBrainMapImage();
        
        // Draw LEDs
        this.drawLeds();
    }
    
    
    drawLeds() {
        this.ledPositions.forEach(ledPos => {
            const [x1, y1, x2, y2] = ledPos.coords;
            
            // Draw LED rectangle if selected (using BigInt)
            if (this.ledSelectionValue & (1n << BigInt(ledPos.bit))) {
                this.ctx.fillStyle = 'rgba(0, 190, 255, 1)';
                this.ctx.strokeStyle = 'rgb(0, 190, 255)';
                this.ctx.lineWidth = 2;
                this.ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
                this.ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
            }
            else {
                // Draw unselected LED border
                this.ctx.strokeStyle = 'rgb(0, 190, 255)';
                this.ctx.lineWidth = 2;
                this.ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
            }
            
            // Draw X overlay if LED is broken (bit is 0 in check mask)
            const ledBit = BigInt(ledPos.bit);
            const isLedBroken = (this.ledCheckMask & (1n << ledBit)) === 0n;
            
            if (isLedBroken) {
                this.ctx.strokeStyle = 'red';
                this.ctx.lineWidth = 3;
                this.ctx.beginPath();
                this.ctx.moveTo(x1, y1);
                this.ctx.lineTo(x2, y2);
                this.ctx.moveTo(x1, y2);
                this.ctx.lineTo(x2, y1);
                this.ctx.stroke();
                
            }
            
            // Always draw LED number
            this.ctx.fillStyle = 'black';
            this.ctx.font = 'bold 10px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            
            const centerX = x1 + (x2 - x1) / 2;
            const centerY = y1 + (y2 - y1) / 2;
            
            this.ctx.fillText((ledPos.bit + 1).toString(), centerX, centerY);
        });
    }
    
    // Method to load actual brain map image when available
    loadBrainMapImage(imagePath) {
        const img = new Image();
        img.onload = () => {
            this.brainMapImage = img;
            this.draw();
        };
        img.onerror = () => {
            console.warn('Could not load brain map image:', imagePath);
        };
        img.src = imagePath;
    }
    
    drawBrainMapImage() {
        if (this.brainMapImage) {
            // Scale image to fit canvas
            const scale = Math.min(this.canvasWidth / this.brainMapImage.width, 
                                 this.canvasHeight / this.brainMapImage.height);
            const width = this.brainMapImage.width * scale;
            const height = this.brainMapImage.height * scale;
            const x = (this.canvasWidth - width) / 2;
            const y = (this.canvasHeight - height) / 2;
            
            this.ctx.drawImage(this.brainMapImage, x, y, width, height);
        }
    }
}