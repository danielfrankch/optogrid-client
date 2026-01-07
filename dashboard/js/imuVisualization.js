/**
 * IMU Visualization for OptoGrid Dashboard
 * Handles 3D IMU orientation display and IMU data plots
 */
class IMUVisualization {
    constructor(canvas3dId, plotCanvasId) {
        this.canvas3d = document.getElementById(canvas3dId);
        this.ctx3d = this.canvas3d ? this.canvas3d.getContext('2d') : null;
        
        this.plotCanvas = document.getElementById(plotCanvasId);
        this.ctxPlot = this.plotCanvas ? this.plotCanvas.getContext('2d') : null;
        
        // IMU data storage
        this.imuData = {
            roll: 0,
            pitch: 0,
            yaw: 0,
            samples: {
                accelX: [],
                accelY: [],
                accelZ: [],
                gyroX: [],
                gyroY: [],
                gyroZ: [],
                timestamps: []
            }
        };
        
        this.maxSamples = 200;
        
        if (this.ctx3d) {
            this.setup3DCanvas();
            this.draw3D();
        }
        
        if (this.ctxPlot) {
            this.setupPlotCanvas();
            this.drawPlot();
        }
        
    }
    
    setup3DCanvas() {
        const rect = this.canvas3d.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        
        this.canvas3d.width = rect.width * dpr;
        this.canvas3d.height = rect.height * dpr;
        
        this.ctx3d.scale(dpr, dpr);
        this.canvas3d.style.width = rect.width + 'px';
        this.canvas3d.style.height = rect.height + 'px';
        
        this.canvas3dWidth = rect.width;
        this.canvas3dHeight = rect.height;
    }
    
    setupPlotCanvas() {
    // Get container dimensions and use more of the available space
    const container = this.plotCanvas.parentElement;
    const containerRect = container.getBoundingClientRect();
    
    // Use more of the container space - reduce padding to allow plots to extend more
    const padding = 1; 
    const maxWidth = containerRect.width - padding;
    const maxHeight = containerRect.height - padding;
    
    const dpr = window.devicePixelRatio || 1;
    
    this.plotCanvas.width = maxWidth * dpr;
    this.plotCanvas.height = maxHeight * dpr;
    
    this.ctxPlot.scale(dpr, dpr);
    this.plotCanvas.style.width = maxWidth + 'px';
    this.plotCanvas.style.height = maxHeight + 'px';
    
    this.plotCanvasWidth = maxWidth;
    this.plotCanvasHeight = maxHeight;
    }   
    
    updateIMU(roll, pitch, yaw, imuValues = null) {
        this.imuData.roll = roll;
        this.imuData.pitch = pitch;
        this.imuData.yaw = yaw;
        
        if (imuValues && imuValues.length >= 6) {
            const timestamp = Date.now();
            
            // Add new samples
            this.imuData.samples.accelX.push(imuValues[0]);
            this.imuData.samples.accelY.push(imuValues[1]);
            this.imuData.samples.accelZ.push(imuValues[2]);
            this.imuData.samples.gyroX.push(imuValues[3]);
            this.imuData.samples.gyroY.push(imuValues[4]);
            this.imuData.samples.gyroZ.push(imuValues[5]);
            this.imuData.samples.timestamps.push(timestamp);
            
            // Limit to maxSamples
            Object.keys(this.imuData.samples).forEach(key => {
                if (this.imuData.samples[key].length > this.maxSamples) {
                    this.imuData.samples[key] = this.imuData.samples[key].slice(-this.maxSamples);
                }
            });
        }
        
        this.draw3D();
        this.drawPlot();
    }
    
    draw3D() {
        if (!this.ctx3d) return;
        
        // Clear canvas
        this.ctx3d.clearRect(0, 0, this.canvas3dWidth, this.canvas3dHeight);
        
        // Draw 3D cube representing IMU orientation
        const centerX = this.canvas3dWidth / 2;
        const centerY = this.canvas3dHeight / 2;
        const size = 30;
        
        // Convert degrees to radians
        const rollRad = this.imuData.roll * Math.PI / 180;
        const pitchRad = this.imuData.pitch * Math.PI / 180;
        const yawRad = this.imuData.yaw * Math.PI / 180;
        
        // Draw cube faces with rotation
        this.ctx3d.save();
        this.ctx3d.translate(centerX, centerY);
        
        // Simple 2D representation of 3D rotation
        const rotatedSize = size * (0.7 + 0.3 * Math.cos(pitchRad));
        
        // Main cube face
        this.ctx3d.fillStyle = 'rgba(52, 152, 219, 0.7)';
        this.ctx3d.strokeStyle = '#2980b9';
        this.ctx3d.lineWidth = 2;
        
        this.ctx3d.save();
        this.ctx3d.rotate(rollRad);
        this.ctx3d.fillRect(-rotatedSize/2, -rotatedSize/2, rotatedSize, rotatedSize);
        this.ctx3d.strokeRect(-rotatedSize/2, -rotatedSize/2, rotatedSize, rotatedSize);
        
        // Draw orientation indicators
        this.ctx3d.strokeStyle = '#e74c3c';
        this.ctx3d.lineWidth = 3;
        this.ctx3d.beginPath();
        this.ctx3d.moveTo(0, -rotatedSize/2);
        this.ctx3d.lineTo(0, -rotatedSize/2 - 10);
        this.ctx3d.stroke();
        
        this.ctx3d.restore();
        this.ctx3d.restore();
        
        // Draw orientation text
        this.ctx3d.fillStyle = '#2c3e50';
        this.ctx3d.font = '12px Arial';
        this.ctx3d.textAlign = 'left';
        this.ctx3d.fillText(`Roll: ${this.imuData.roll.toFixed(1)}°`, 10, 20);
        this.ctx3d.fillText(`Pitch: ${this.imuData.pitch.toFixed(1)}°`, 10, 35);
        this.ctx3d.fillText(`Yaw: ${this.imuData.yaw.toFixed(1)}°`, 10, 50);
    }
    
    drawPlot() {
        if (!this.ctxPlot) return;
        
        // Clear canvas
        this.ctxPlot.clearRect(0, 0, this.plotCanvasWidth, this.plotCanvasHeight);
        
        // Draw background
        this.ctxPlot.fillStyle = '#fafafa';
        this.ctxPlot.fillRect(0, 0, this.plotCanvasWidth, this.plotCanvasHeight);
        
        const margin = 40;
        const plotWidth = this.plotCanvasWidth - 2 * margin;
        const plotHeight = (this.plotCanvasHeight - 3 * margin) / 2;
        
        // Draw accelerometer data
        this.drawSubPlot(
            margin, margin, plotWidth, plotHeight,
            'Accelerometer (g)',
            ['accelX', 'accelY', 'accelZ'],
            ['#e74c3c', '#2ecc71', '#3498db']
        );
        
        // Draw gyroscope data
        this.drawSubPlot(
            margin, margin * 2 + plotHeight, plotWidth, plotHeight,
            'Gyroscope (°/s)',
            ['gyroX', 'gyroY', 'gyroZ'],
            ['#f39c12', '#9b59b6', '#1abc9c']
        );
    }
    
    drawSubPlot(x, y, width, height, title, dataKeys, colors) {
        // Draw plot background
        this.ctxPlot.fillStyle = 'white';
        this.ctxPlot.fillRect(x, y, width, height);
        this.ctxPlot.strokeStyle = '#dee2e6';
        this.ctxPlot.lineWidth = 1;
        this.ctxPlot.strokeRect(x, y, width, height);
        
        // Draw title
        this.ctxPlot.fillStyle = '#2c3e50';
        this.ctxPlot.font = 'bold 12px Arial';
        this.ctxPlot.textAlign = 'left';
        this.ctxPlot.fillText(title, x, y - 5);
        
        // Find data range
        let minVal = Infinity;
        let maxVal = -Infinity;
        
        dataKeys.forEach(key => {
            if (this.imuData.samples[key].length > 0) {
                const keyMin = Math.min(...this.imuData.samples[key]);
                const keyMax = Math.max(...this.imuData.samples[key]);
                minVal = Math.min(minVal, keyMin);
                maxVal = Math.max(maxVal, keyMax);
            }
        });
        
        if (minVal === maxVal) {
            minVal -= 1;
            maxVal += 1;
        }
        
        const range = maxVal - minVal;
        
        // Draw grid lines
        this.ctxPlot.strokeStyle = '#f8f9fa';
        this.ctxPlot.lineWidth = 1;
        for (let i = 1; i < 5; i++) {
            const gridY = y + (height * i) / 5;
            this.ctxPlot.beginPath();
            this.ctxPlot.moveTo(x, gridY);
            this.ctxPlot.lineTo(x + width, gridY);
            this.ctxPlot.stroke();
        }
        
        // Draw data lines
        dataKeys.forEach((key, index) => {
            const data = this.imuData.samples[key];
            if (data.length < 2) return;
            
            this.ctxPlot.strokeStyle = colors[index];
            this.ctxPlot.lineWidth = 2;
            this.ctxPlot.beginPath();
            
            for (let i = 0; i < data.length; i++) {
                const plotX = x + (width * i) / (this.maxSamples - 1);
                const plotY = y + height - ((data[i] - minVal) / range) * height;
                
                if (i === 0) {
                    this.ctxPlot.moveTo(plotX, plotY);
                } else {
                    this.ctxPlot.lineTo(plotX, plotY);
                }
            }
            
            this.ctxPlot.stroke();
        });
        
        // Draw axis labels
        this.ctxPlot.fillStyle = '#6c757d';
        this.ctxPlot.font = '10px Arial';
        this.ctxPlot.textAlign = 'right';
        this.ctxPlot.fillText(maxVal.toFixed(2), x - 5, y + 5);
        this.ctxPlot.fillText(minVal.toFixed(2), x - 5, y + height);
        
        // Draw legend
        dataKeys.forEach((key, index) => {
            const legendX = x + width - 100 + (index * 30);
            const legendY = y + 15;
            
            this.ctxPlot.strokeStyle = colors[index];
            this.ctxPlot.lineWidth = 2;
            this.ctxPlot.beginPath();
            this.ctxPlot.moveTo(legendX, legendY);
            this.ctxPlot.lineTo(legendX + 15, legendY);
            this.ctxPlot.stroke();
            
            this.ctxPlot.fillStyle = '#2c3e50';
            this.ctxPlot.font = '10px Arial';
            this.ctxPlot.textAlign = 'left';
            this.ctxPlot.fillText(key.charAt(key.length - 1).toUpperCase(), legendX + 18, legendY + 3);
        });
    }
    
}