// server.js

const express = require('express');
const path = require('path');
const app = express();
const port = 3001;

app.use('/videos', express.static('/Users/vamsikeshwaran/Desktop/DataSet'));

app.get('/api/video', (req, res) => {
    const { text } = req.query;
    if (text) {
        const videoPath = path.join('/Users/vamsikeshwaran/Desktop/DataSet', `${text}.mp4`);
        res.sendFile(videoPath, err => {
            if (err) {
                res.status(404).json({ error: 'Video not found' });
            }
        });
    } else {
        res.status(400).json({ error: 'Text query parameter is required' });
    }
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
