import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QComboBox, QProgressBar, QFormLayout, QGroupBox)
from PyQt5.QtCore import QThread, pyqtSignal

import ffmpeg

class ConversionThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, input_file, output_file, output_format, video_bitrate, audio_bitrate, resolution):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.output_format = output_format
        self.video_bitrate = video_bitrate
        self.audio_bitrate = audio_bitrate
        self.resolution = resolution

    def run(self):
        try:
            # Get input file information
            probe = ffmpeg.probe(self.input_file)
            duration = float(probe['format']['duration'])
            
            # Set up ffmpeg stream
            stream = ffmpeg.input(self.input_file)
            
            # Prepare output arguments
            output_args = {}
            if self.video_bitrate and self.output_format in ['mp4', 'avi', 'mkv', 'webm', 'mov', 'flv']:
                output_args['video_bitrate'] = self.video_bitrate
            if self.audio_bitrate:
                output_args['audio_bitrate'] = self.audio_bitrate
            if self.resolution and self.output_format in ['mp4', 'avi', 'mkv', 'webm', 'mov', 'flv']:
                width, height = map(int, self.resolution.split('x'))
                output_args['vf'] = f'scale={width}:{height}'
            
            # Handle different conversion scenarios
            if self.output_format in ['mp4', 'avi', 'mkv', 'webm', 'mov', 'flv']:
                output_args.update({'vcodec': 'libx264', 'acodec': 'aac'})
            elif self.output_format in ['mp3', 'wav', 'flac', 'ogg', 'aac']:
                if self.output_format == 'mp3':
                    output_args['acodec'] = 'libmp3lame'
                elif self.output_format == 'ogg':
                    output_args['acodec'] = 'libvorbis'
                elif self.output_format == 'aac':
                    output_args['acodec'] = 'aac'
            else:
                raise ValueError(f"Unsupported output format: {self.output_format}")
            
            stream = ffmpeg.output(stream, self.output_file, **output_args)
            
            # Run the ffmpeg command
            process = ffmpeg.run_async(stream, pipe_stdout=True, pipe_stderr=True)
            
            while True:
                output = process.stderr.readline().decode()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    parts = output.split('=')
                    if len(parts) == 2 and parts[0].strip() == 'out_time_ms':
                        time = float(parts[1].strip()) / 1000000
                        progress = min(int(time / duration * 100), 100)
                        self.progress.emit(progress)
            
            self.finished.emit(True, "Conversion successful")
        except Exception as e:
            self.finished.emit(False, str(e))

class MediaConverterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Advanced Media Converter')
        self.setGeometry(100, 100, 500, 400)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Input file selection
        input_layout = QHBoxLayout()
        self.input_label = QLabel('Input File:')
        self.input_button = QPushButton('Select File')
        self.input_button.clicked.connect(self.select_input_file)
        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.input_button)
        main_layout.addLayout(input_layout)

        # Output format selection
        format_layout = QHBoxLayout()
        self.format_label = QLabel('Output Format:')
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            'mp4 (Video)',
            'avi (Video)',
            'mkv (Video)',
            'webm (Video)',
            'mov (Video)',
            'flv (Video)',
            'mp3 (Audio)',
            'wav (Audio)',
            'flac (Audio)',
            'ogg (Audio)',
            'aac (Audio)'
        ])
        self.format_combo.currentTextChanged.connect(self.update_visible_options)
        format_layout.addWidget(self.format_label)
        format_layout.addWidget(self.format_combo)
        main_layout.addLayout(format_layout)

        # Advanced options
        self.options_group = QGroupBox("Advanced Options")
        self.options_layout = QFormLayout()

        self.video_bitrate_combo = QComboBox()
        self.video_bitrate_combo.addItems(['500k', '1M', '2M', '5M', '10M', '20M'])
        self.video_bitrate_combo.setCurrentText('5M')
        self.video_bitrate_label = QLabel('Video Bitrate (Video only):')
        self.options_layout.addRow(self.video_bitrate_label, self.video_bitrate_combo)

        self.audio_bitrate_combo = QComboBox()
        self.audio_bitrate_combo.addItems(['64k', '128k', '192k', '256k', '320k'])
        self.audio_bitrate_combo.setCurrentText('192k')
        self.audio_bitrate_label = QLabel('Audio Bitrate:')
        self.options_layout.addRow(self.audio_bitrate_label, self.audio_bitrate_combo)

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(['640x480', '1280x720', '1920x1080', '3840x2160'])
        self.resolution_combo.setCurrentText('1280x720')
        self.resolution_label = QLabel('Resolution (Video only):')
        self.options_layout.addRow(self.resolution_label, self.resolution_combo)

        self.options_group.setLayout(self.options_layout)
        main_layout.addWidget(self.options_group)

        # Convert button
        self.convert_button = QPushButton('Convert')
        self.convert_button.clicked.connect(self.start_conversion)
        main_layout.addWidget(self.convert_button)

        # Progress bar
        self.progress_bar = QProgressBar()
        main_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel('')
        main_layout.addWidget(self.status_label)

        self.input_file = ''
        self.output_file = ''

        # Initial update of visible options
        self.update_visible_options()

    def select_input_file(self):
        self.input_file, _ = QFileDialog.getOpenFileName(self, "Select Input File")
        if self.input_file:
            self.input_label.setText(f"Input File: {os.path.basename(self.input_file)}")

    def update_visible_options(self):
        output_format = self.format_combo.currentText().split()[0]
        is_video = output_format in ['mp4', 'avi', 'mkv', 'webm', 'mov', 'flv']
        self.video_bitrate_label.setVisible(is_video)
        self.video_bitrate_combo.setVisible(is_video)
        self.resolution_label.setVisible(is_video)
        self.resolution_combo.setVisible(is_video)

    def start_conversion(self):
        if not self.input_file:
            self.status_label.setText("Please select an input file.")
            return

        output_format = self.format_combo.currentText().split()[0]
        self.output_file, _ = QFileDialog.getSaveFileName(self, "Save Output File", "", f"*.{output_format}")
        
        if self.output_file:
            self.convert_button.setEnabled(False)
            self.progress_bar.setValue(0)
            self.status_label.setText("Converting...")

            video_bitrate = self.video_bitrate_combo.currentText() if self.video_bitrate_combo.isVisible() else None
            audio_bitrate = self.audio_bitrate_combo.currentText()
            resolution = self.resolution_combo.currentText() if self.resolution_combo.isVisible() else None

            self.conversion_thread = ConversionThread(
                self.input_file, self.output_file, output_format, 
                video_bitrate, audio_bitrate, resolution
            )
            self.conversion_thread.progress.connect(self.update_progress)
            self.conversion_thread.finished.connect(self.conversion_finished)
            self.conversion_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def conversion_finished(self, success, message):
        self.convert_button.setEnabled(True)
        if success:
            self.status_label.setText("Conversion completed successfully.")
        else:
            self.status_label.setText(f"Conversion failed: {message}")

def main():
    app = QApplication(sys.argv)
    ex = MediaConverterGUI()
    ex.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()