/**
 * IMU Visualization for OptoGrid Dashboard
 * Handles 3D IMU orientation display and IMU data plots
 */
class IMUVisualization {
    constructor(canvas3dId, plotCanvasId) {
        this.canvas3d = document.getElementById(canvas3dId);
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
        
        // Three.js setup for 3D visualization
        if (this.canvas3d) {
            this.setupThreeJS();
        }
        
        if (this.ctxPlot) {
            this.setupPlotCanvas();
            this.drawPlot();
        }
    }
    
    setupThreeJS() {
        // Create Three.js scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x8cb8c4); // Match OpenGL background (0.5, 0.6, 0.6)
        
        // Setup camera with perspective matching OpenGL - use larger dimension for better space utilization
        const rect = this.canvas3d.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height) * 0.9; // Use 90% of larger dimension
        
        this.camera = new THREE.PerspectiveCamera(45, 1.0, 0.1, 100.0); // Keep 1:1 aspect ratio
        this.camera.position.set(0, 0, 6); // Match OpenGL camera distance
        this.camera.lookAt(0, 0, 0);
        
        // Create WebGL renderer with square dimensions
        this.renderer = new THREE.WebGLRenderer({ 
            canvas: this.canvas3d, 
            antialias: true,
            alpha: false 
        });
        this.renderer.setSize(size, size); // Set square size
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        
        // Enable depth testing (equivalent to glEnable(GL_DEPTH_TEST))
        this.renderer.sortObjects = true;
        
        // Create rat head model
        this.createRatHeadModel();
        
        // Create coordinate system
        this.createCoordinateSystem();
        
        // Add orbit controls for mouse interaction
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.enableZoom = true;
        this.controls.enablePan = true;
        this.controls.target.set(0, 0, 0);
        
        // 60FPS limiting variables
        this.lastRenderTime = 0;
        this.targetFPS = 60;
        this.frameInterval = 1000 / this.targetFPS; // ~16.67ms for 60fps
        
        // Start animation loop
        this.animate();
        
        // Handle window resize
        window.addEventListener('resize', () => this.onWindowResize());
    }
    
    createRatHeadModel() {
        // Create rat head group (equivalent to OpenGL transformations)
        this.ratHeadGroup = new THREE.Group();
        
        // 1. Main head (ellipsoid) - pinkish color
        this.createHeadEllipsoid();
        
        // 2. Snout (cone) - dark
        this.createSnout();
        
        // 3. Left ear (ellipsoid) - Dark
        this.createLeftEar();
        
        // 4. Right ear (ellipsoid) - Dark
        this.createRightEar();
        
        // 5. Eyes (two small spheres)
        this.createEyes();
        
        this.scene.add(this.ratHeadGroup);
    }
    
    createHeadEllipsoid() {
        // Create ellipsoid geometry (scaled sphere)
        const headGeometry = new THREE.SphereGeometry(1, 16, 12);
        const headMaterial = new THREE.MeshBasicMaterial({ 
            color: 0xe6b3b3 // Light pink (0.9, 0.7, 0.7)
        });
        const head = new THREE.Mesh(headGeometry, headMaterial);
        
        // Apply scaling: glScalef(0.8, 0.6, 1.0) * scale factor 1.5
        head.scale.set(0.8 * 1.5, 0.6 * 2.0, 1.0 * 1.5);
        
        this.ratHeadGroup.add(head);
    }
    
    createSnout() {
        // Create cone geometry
        const snoutGeometry = new THREE.ConeGeometry(0.5, 1.0, 8);
        const snoutMaterial = new THREE.MeshBasicMaterial({ 
            color: 0x333333 // Dark (0.2, 0.2, 0.2)
        });
        const snout = new THREE.Mesh(snoutGeometry, snoutMaterial);
        
        // Position and rotate: glTranslatef(0, 0, 1.5), glScalef(0.6, 0.6, 0.4)
        snout.position.set(0, 0, 1.5);
        snout.scale.set(0.6, 0.4, 0.6); // Note: cone height is Y, so adjust accordingly
        snout.rotation.x = -Math.PI / 2; // Point in +Z direction
        
        this.ratHeadGroup.add(snout);
    }
    
    createLeftEar() {
        // Create ellipsoid for ear
        const earGeometry = new THREE.SphereGeometry(1, 12, 8);
        const earMaterial = new THREE.MeshBasicMaterial({ 
            color: 0x33334d // Dark blue-grey (0.2, 0.2, 0.3)
        });
        const leftEar = new THREE.Mesh(earGeometry, earMaterial);
        
        // Apply transformations: glTranslatef(-1.0, 0.7, -0.2), glRotatef(30, 0, 0, 1), glScalef(0.8, 0.9, 0.3)
        leftEar.position.set(-1.0, 0.7, -0.2);
        leftEar.rotation.z = 30 * Math.PI / 180; // Convert degrees to radians
        leftEar.scale.set(0.8, 0.9, 0.3);
        
        this.ratHeadGroup.add(leftEar);
    }
    
    createRightEar() {
        // Create ellipsoid for ear
        const earGeometry = new THREE.SphereGeometry(1, 12, 8);
        const earMaterial = new THREE.MeshBasicMaterial({ 
            color: 0x33334d // Dark blue-grey (0.2, 0.2, 0.3)
        });
        const rightEar = new THREE.Mesh(earGeometry, earMaterial);
        
        // Apply transformations: glTranslatef(1.0, 0.7, -0.2), glRotatef(-30, 0, 0, 1), glScalef(0.8, 0.9, 0.3)
        rightEar.position.set(1.0, 0.7, -0.2);
        rightEar.rotation.z = -30 * Math.PI / 180; // Convert degrees to radians
        rightEar.scale.set(0.8, 0.9, 0.3);
        
        this.ratHeadGroup.add(rightEar);
    }
    
    createEyes() {
        // Create eye geometry and material
        const eyeGeometry = new THREE.SphereGeometry(1, 8, 6);
        const eyeMaterial = new THREE.MeshBasicMaterial({ 
            color: 0x1a1a1a // Black (0.1, 0.1, 0.1)
        });
        
        // Left eye
        const leftEye = new THREE.Mesh(eyeGeometry, eyeMaterial);
        leftEye.position.set(-0.5, 0.5, 1.0);
        leftEye.scale.set(0.2, 0.2, 0.2);
        this.ratHeadGroup.add(leftEye);
        
        // Right eye
        const rightEye = new THREE.Mesh(eyeGeometry, eyeMaterial);
        rightEye.position.set(0.5, 0.5, 1.0);
        rightEye.scale.set(0.2, 0.2, 0.2);
        this.ratHeadGroup.add(rightEye);
    }
    
    createCoordinateSystem() {
        // Create coordinate axes with thick lines
        const axesGroup = new THREE.Group();
        
        // Create line material with thicker width (Note: lineWidth may not work in all browsers)
        const createAxisLine = (color, start, end) => {
            const geometry = new THREE.BufferGeometry().setFromPoints([start, end]);
            const material = new THREE.LineBasicMaterial({ color: color, linewidth: 3 });
            return new THREE.Line(geometry, material);
        };
        
        // X axis (red) - pointing right
        const xAxis = createAxisLine(0xff0000, new THREE.Vector3(0, 0, 0), new THREE.Vector3(2, 0, 0));
        axesGroup.add(xAxis);
        
        // Y axis (green) - pointing up
        const yAxis = createAxisLine(0x00ff00, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 2, 0));
        axesGroup.add(yAxis);
        
        // Z axis (blue) - pointing forward
        const zAxis = createAxisLine(0x0000ff, new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, 3));
        axesGroup.add(zAxis);
        
        // Alternative: Use AxesHelper for thicker, more visible axes
        const axesHelper = new THREE.AxesHelper(2);
        axesHelper.position.set(0, 0, 0);
        
        this.scene.add(axesHelper);
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        
        // 60FPS limiting - only render if enough time has passed
        const now = performance.now();
        const elapsed = now - this.lastRenderTime;
        
        if (elapsed >= this.frameInterval) {
            // Update controls
            this.controls.update();
            
            // Render scene
            this.renderer.render(this.scene, this.camera);
            
            this.lastRenderTime = now - (elapsed % this.frameInterval);
        }
    }
    
    onWindowResize() {
        if (!this.canvas3d) return;
        
        const rect = this.canvas3d.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height) * 0.9; // Use 90% of larger dimension
        
        this.camera.aspect = 1.0; // Always square aspect ratio
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(size, size);
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
        
        // Update 3D model rotation
        this.update3DRotation();
        this.drawPlot();
    }
    
    update3DRotation() {
        if (!this.ratHeadGroup) return;
        
        // Convert degrees to radians - matching OpenGL rotation order
        const pitchRad = this.imuData.pitch * Math.PI / 180;
        const rollRad = -this.imuData.roll * Math.PI / 180;  // Negative to match OpenGL
        const yawRad = this.imuData.yaw * Math.PI / 180;
        
        // Apply rotations in the same order as OpenGL:
        // glRotatef(pitch, 1, 0, 0)
        // glRotatef(-roll, 0, 0, 1) 
        // glRotatef(yaw, 0, 1, 0)
        
        // Reset rotation
        this.ratHeadGroup.rotation.set(0, 0, 0);
        
        // Apply rotations in order (Three.js uses ZYX Euler order by default)
        this.ratHeadGroup.rotation.order = 'XZY'; // Custom order to match OpenGL
        this.ratHeadGroup.rotation.x = pitchRad;   // Pitch around X
        this.ratHeadGroup.rotation.z = rollRad;    // Roll around Z
        this.ratHeadGroup.rotation.y = yawRad;     // Yaw around Y
    }
    
    draw3D() {
        if (!this.ctx3d) return;
        
        // Clear canvas
        this.ctx3d.clearRect(0, 0, this.canvas3dWidth, this.canvas3dHeight);
        
        // Draw enhanced 3D-like cube representing IMU orientation
        const centerX = this.canvas3dWidth / 2;
        const centerY = this.canvas3dHeight / 2;
        const size = 40;
        
        // Convert degrees to radians
        const rollRad = this.imuData.roll * Math.PI / 180;
        const pitchRad = this.imuData.pitch * Math.PI / 180;
        const yawRad = this.imuData.yaw * Math.PI / 180;
        
        this.ctx3d.save();
        this.ctx3d.translate(centerX, centerY);
        
        // Enhanced 3D cube simulation with multiple faces
        // Calculate pseudo-3D projection based on pitch
        const scale = 0.7 + 0.3 * Math.cos(pitchRad);
        const skewX = Math.sin(yawRad) * 0.3;
        const skewY = Math.sin(pitchRad) * 0.3;
        
        // Draw back face (darker)
        this.ctx3d.save();
        this.ctx3d.transform(1, skewY, skewX, scale, 8, 8);
        this.ctx3d.rotate(rollRad);
        this.ctx3d.fillStyle = 'rgba(52, 152, 219, 0.3)';
        this.ctx3d.fillRect(-size/2, -size/2, size, size);
        this.ctx3d.strokeStyle = '#2980b9';
        this.ctx3d.lineWidth = 1;
        this.ctx3d.strokeRect(-size/2, -size/2, size, size);
        this.ctx3d.restore();
        
        // Draw main front face
        this.ctx3d.save();
        this.ctx3d.transform(1, skewY, skewX, scale, 0, 0);
        this.ctx3d.rotate(rollRad);
        this.ctx3d.fillStyle = 'rgba(52, 152, 219, 0.8)';
        this.ctx3d.fillRect(-size/2, -size/2, size, size);
        this.ctx3d.strokeStyle = '#2980b9';
        this.ctx3d.lineWidth = 2;
        this.ctx3d.strokeRect(-size/2, -size/2, size, size);
        
        // Draw orientation indicator (red arrow pointing "up")
        this.ctx3d.strokeStyle = '#e74c3c';
        this.ctx3d.fillStyle = '#e74c3c';
        this.ctx3d.lineWidth = 3;
        
        // Arrow shaft
        this.ctx3d.beginPath();
        this.ctx3d.moveTo(0, -size/2);
        this.ctx3d.lineTo(0, -size/2 - 15);
        this.ctx3d.stroke();
        
        // Arrow head
        this.ctx3d.beginPath();
        this.ctx3d.moveTo(0, -size/2 - 15);
        this.ctx3d.lineTo(-5, -size/2 - 10);
        this.ctx3d.lineTo(5, -size/2 - 10);
        this.ctx3d.closePath();
        this.ctx3d.fill();
        
        this.ctx3d.restore();
        this.ctx3d.restore();
        
        // Draw coordinate system
        this.drawCoordinateSystem(centerX + 80, centerY, 30);
        
        // Draw orientation text with background
        this.ctx3d.fillStyle = 'rgba(255, 255, 255, 0.9)';
        this.ctx3d.fillRect(5, 5, 110, 55);
        this.ctx3d.strokeStyle = '#bdc3c7';
        this.ctx3d.lineWidth = 1;
        this.ctx3d.strokeRect(5, 5, 110, 55);
        
        this.ctx3d.fillStyle = '#2c3e50';
        this.ctx3d.font = 'bold 12px monospace';
        this.ctx3d.textAlign = 'left';
        this.ctx3d.fillText(`Roll:  ${this.imuData.roll.toFixed(1)}°`, 10, 20);
        this.ctx3d.fillText(`Pitch: ${this.imuData.pitch.toFixed(1)}°`, 10, 35);
        this.ctx3d.fillText(`Yaw:   ${this.imuData.yaw.toFixed(1)}°`, 10, 50);
    }
    
    drawCoordinateSystem(centerX, centerY, size) {
        this.ctx3d.save();
        this.ctx3d.translate(centerX, centerY);
        
        // X-axis (red)
        this.ctx3d.strokeStyle = '#e74c3c';
        this.ctx3d.lineWidth = 2;
        this.ctx3d.beginPath();
        this.ctx3d.moveTo(0, 0);
        this.ctx3d.lineTo(size, 0);
        this.ctx3d.stroke();
        this.ctx3d.fillStyle = '#e74c3c';
        this.ctx3d.font = '10px Arial';
        this.ctx3d.fillText('X', size + 5, 5);
        
        // Y-axis (green)
        this.ctx3d.strokeStyle = '#27ae60';
        this.ctx3d.beginPath();
        this.ctx3d.moveTo(0, 0);
        this.ctx3d.lineTo(0, -size);
        this.ctx3d.stroke();
        this.ctx3d.fillStyle = '#27ae60';
        this.ctx3d.fillText('Y', -5, -size - 5);
        
        // Z-axis (blue) - simulated with diagonal
        this.ctx3d.strokeStyle = '#3498db';
        this.ctx3d.beginPath();
        this.ctx3d.moveTo(0, 0);
        this.ctx3d.lineTo(-size * 0.7, size * 0.7);
        this.ctx3d.stroke();
        this.ctx3d.fillStyle = '#3498db';
        this.ctx3d.fillText('Z', -size * 0.7 - 10, size * 0.7 + 5);
        
        this.ctx3d.restore();
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