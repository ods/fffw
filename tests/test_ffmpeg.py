# coding: utf-8

# $Id: $
from unittest import TestCase

from fffw.encoding import FFMPEG, Muxer, VideoCodec, AudioCodec
from fffw.encoding.muxer import HLSMuxer, TeeMuxer
from fffw.graph import filters
from fffw.graph.base import SourceFile, LavfiSource, VIDEO, AUDIO
from fffw.wrapper import ensure_binary


# noinspection PyPep8Naming
def SimpleMuxer(name):
    muxer_type = type('%sMuxer' % name.upper(), (Muxer,), {'format': name})
    return muxer_type


class FFMPEGTestCase(TestCase):

    def testFFMPEG(self):
        """ Проверка работоспособности и демонстрация возможностей."""
        ff = FFMPEG()
        ff < SourceFile('/tmp/input.mp4')

        fc = ff.init_filter_complex()

        asplit = fc.audio | filters.AudioSplit()

        fc.video | filters.Scale(640, 360) | fc.get_video_dest(0)

        asplit.connect_dest(fc.get_audio_dest(0))
        asplit.connect_dest(fc.get_audio_dest(1))

        out0 = SimpleMuxer('flv')('/tmp/out.flv')
        out1 = SimpleMuxer('mp3')('/tmp/out.mp3')

        cv0 = VideoCodec(vcodec='libx264', vbitrate='700000', size='640x360')
        ca0 = AudioCodec(acodec='aac', abitrate='128000')
        ca1 = AudioCodec(acodec='libmp3lame', abitrate='394000')

        ff.add_output(out0, cv0, ca0)
        ff.add_output(out1, ca1)

        expected = [
            'ffmpeg',
            '-i', '/tmp/input.mp4',
            '-filter_complex',
            '[0:v]scale=640x360[vout0];[0:a]asplit[aout0][aout1]',

            '-map', '[vout0]', '-c:v', 'libx264', '-b:v', '700000',
            '-map', '[aout0]', '-c:a', 'aac', '-b:a', '128000',

            '-f', 'flv',
            '/tmp/out.flv',

            '-map', '[aout1]', '-c:a', 'libmp3lame', '-b:a', '394000',
            '-f', 'mp3',
            '/tmp/out.mp3'
        ]
        self.assertEqual(ff.get_args(), ensure_binary(expected))

    def testBypassWithFilterComplex(self):
        """ Проверка работы в режиме bypass, когда аудиопоток не проходит ни
        через один фильтр."""
        ff = FFMPEG(inputfile=SourceFile('/tmp/input.mp4'))

        fc = ff.init_filter_complex()
        fc.video | filters.Scale(640, 360) | fc.get_video_dest(0)

        cv0 = VideoCodec(vcodec='libx264', vbitrate='700000', size='640x360')
        ca0 = AudioCodec(acodec='aac', abitrate='128000')
        out0 = SimpleMuxer('flv')('/tmp/out.flv')
        ff.add_output(out0, cv0, ca0)

        expected = [
            'ffmpeg',
            '-i', '/tmp/input.mp4',
            '-filter_complex',
            '[0:v]scale=640x360[vout0]',
            '-map', '[vout0]', '-c:v', 'libx264', '-b:v', '700000',
            '-map', '0:a', '-c:a', 'aac', '-b:a', '128000',
            '-f', 'flv',
            '/tmp/out.flv'
        ]
        self.assertEqual(ff.get_args(), ensure_binary(expected))

    def testBypassWithoutFilterComplex(self):
        """ Проверка работы в режиме bypass, когда вообще нет filter_complex."""
        ff = FFMPEG(inputfile=SourceFile('/tmp/input.mp4'))

        cv0 = VideoCodec(vcodec='libx264', vbitrate='700000', size='640x360')
        ca0 = AudioCodec(acodec='aac', abitrate='128000')
        out0 = SimpleMuxer('flv')('/tmp/out.flv')
        ff.add_output(out0, cv0, ca0)

        expected = [
            'ffmpeg',
            '-i', '/tmp/input.mp4',
            '-map', '0:v', '-c:v', 'libx264', '-b:v', '700000',
            '-map', '0:a', '-c:a', 'aac', '-b:a', '128000',
            '-f', 'flv',
            '/tmp/out.flv'
        ]
        self.assertEqual(ff.get_args(), ensure_binary(expected))

    def testInputSkipStreams(self):
        """ Проверка корректности наименования входных потоков в фильтрах."""

        ff = FFMPEG()
        ff < SourceFile('/tmp/input.jpg', audio_streams=0)
        ff < SourceFile('/tmp/input.mp4')
        fc = ff.init_filter_complex()
        overlay = filters.Overlay(0, 0)
        fc.video | filters.Scale(640, 360) | overlay
        fc.video | filters.Scale(1280, 720) | overlay
        fc.audio | filters.Volume(-20) | fc.get_audio_dest(0)
        overlay | fc.get_video_dest(0)

        cv0 = VideoCodec(vcodec='libx264', vbitrate='700000', size='640x360')
        ca0 = AudioCodec(acodec='aac', abitrate='128000')
        out0 = SimpleMuxer('flv')('/tmp/out.flv')
        ff.add_output(out0, cv0, ca0)

        expected = [
            'ffmpeg',
            '-i', '/tmp/input.jpg',
            '-i', '/tmp/input.mp4',
            '-filter_complex',
            (
                '[0:v]scale=640x360[v:scale0];'
                '[v:scale0][v:overlay0]overlay=x=0:y=0[vout0];'
                '[1:v]scale=1280x720[v:overlay0];'
                '[1:a]volume=-20.00[aout0]'),
            '-map', '[vout0]', '-c:v', 'libx264', '-b:v', '700000',
            '-map', '[aout0]', '-c:a', 'aac', '-b:a', '128000',
            '-f', 'flv',
            '/tmp/out.flv'
        ]
        self.assertEqual(ff.get_args(), ensure_binary(expected))

    def testCodecCopy(self):
        """ Проверяется корректность использования vcodec=copy совместно с
        фильтрами для аудио."""
        ff = FFMPEG(inputfile=SourceFile('/tmp/input.mp4'))

        fc = ff.init_filter_complex()

        fc.audio | filters.Volume(20) | fc.get_audio_dest(0)

        cv0 = VideoCodec(vcodec='copy')
        ca0 = AudioCodec(acodec='aac', abitrate='128000')
        out0 = SimpleMuxer('flv')('/tmp/out.flv')
        ff.add_output(out0, cv0, ca0)
        expected = [
            'ffmpeg',
            '-i', '/tmp/input.mp4',
            '-filter_complex',
            '[0:a]volume=20.00[aout0]',
            '-map', '0:v',
            '-c:v', 'copy',
            '-map', '[aout0]',
            '-c:a', 'aac', '-b:a', '128000',
            '-f', 'flv',
            '/tmp/out.flv'
        ]
        self.assertEqual(ff.get_args(), ensure_binary(expected))

    def testReuseInputFiles(self):
        """ Проверяет что входные файлы можно использовать несколько раз."""
        ff = FFMPEG(inputfile=SourceFile('/tmp/input.mp4'))
        cv0 = VideoCodec(map='0:v', vcodec='copy')
        ca0 = AudioCodec(map='0:a', acodec='copy')
        out0 = SimpleMuxer('flv')('/tmp/out0.flv')
        ff.add_output(out0, cv0, ca0)

        cv1 = VideoCodec(map='0:v', vcodec='copy')
        ca1 = AudioCodec(map='0:a', acodec='copy')
        out1 = SimpleMuxer('flv')('/tmp/out1.flv')
        ff.add_output(out1, cv1, ca1)
        expected = [
            'ffmpeg',
            '-i', '/tmp/input.mp4',
            '-map', '0:v',
            '-c:v', 'copy',
            '-map', '0:a',
            '-c:a', 'copy',
            '-f', 'flv',
            '/tmp/out0.flv',
            '-map', '0:v',
            '-c:v', 'copy',
            '-map', '0:a',
            '-c:a', 'copy',
            '-f', 'flv',
            '/tmp/out1.flv',
        ]
        self.assertEqual(ff.get_args(), ensure_binary(expected))

    def testCodecCopyWithSplit(self):
        """ Проверяется корректность использования vcodec=copy совместно
        фильтрами для видео."""
        ff = FFMPEG(inputfile=SourceFile('/tmp/input.mp4'))

        fc = ff.init_filter_complex()

        fc.video | filters.Scale(640, 360) | fc.get_video_dest(0)

        cv0 = VideoCodec(map='0:v', vcodec='copy')
        ca0 = AudioCodec(map='0:a', acodec='copy')
        out0 = SimpleMuxer('flv')('/tmp/copy.flv')
        ff.add_output(out0, cv0, ca0)

        cv1 = VideoCodec(vcodec='libx264')
        ca1 = AudioCodec(acodec='aac')
        out1 = SimpleMuxer('flv')('/tmp/out.flv')
        ff.add_output(out1, cv1, ca1)

        expected = [
            'ffmpeg',
            '-i', '/tmp/input.mp4',
            '-filter_complex',
            '[0:v]scale=640x360[vout0]',
            '-map', '0:v',
            '-c:v', 'copy',
            '-map', '0:a',
            '-c:a', 'copy',
            '-f', 'flv',
            '/tmp/copy.flv',
            '-map', '[vout0]',
            '-c:v', 'libx264',
            '-map', '0:a',
            '-c:a', 'aac',
            '-f', 'flv',
            '/tmp/out.flv'

        ]
        self.assertEqual(ff.get_args(), ensure_binary(expected))

    def testLavfiSources(self):
        vsrc = LavfiSource('testsrc', VIDEO, duration=5.3, rate=10)
        asrc = LavfiSource('sine', AUDIO, d=5, b=4)
        ff = FFMPEG(inputfile=[vsrc, asrc])
        ff.add_output(SimpleMuxer('null')('/dev/null'))
        expected = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'testsrc=duration=5.3:rate=10',
            '-f', 'lavfi',
            '-i', 'sine=b=4:d=5',
            '-f', 'null',
            '/dev/null'
        ]
        self.assertEqual(ff.get_args(), ensure_binary(expected))

    def testHLSMuxer(self):
        ff = FFMPEG(inputfile=SourceFile('/tmp/input.mp4'))

        cv0 = VideoCodec(vcodec='libx264')
        ca0 = AudioCodec(acodec='aac')
        out0 = HLSMuxer('http://ya.ru/out.m3u8', segment_size=4,
                        manifest_size=5, method='PUT')
        ff.add_output(out0, cv0, ca0)
        expected = [
            'ffmpeg',
            '-i', '/tmp/input.mp4',
            '-map', '0:v',
            '-c:v', 'libx264',
            '-map', '0:a',
            '-c:a', 'aac',
            '-f', 'hls',
            '-method', 'PUT',
            '-hls_time', '4',
            '-hls_list_size', '5',
            'http://ya.ru/out.m3u8'
        ]
        self.assertEqual(ff.get_args(), ensure_binary(expected))

    def testTeeMuxer(self):
        ff = FFMPEG(inputfile=SourceFile('/tmp/input.mp4'))

        cv0 = VideoCodec(vcodec='libx264')
        ca0 = AudioCodec(acodec='aac')
        out0 = HLSMuxer('http://ya.ru/1.m3u8', segment_size=2)

        out1 = HLSMuxer('http://ya.ru/2.m3u8', manifest_size=5)
        ff.add_output(TeeMuxer(out0, out1), cv0, ca0)

        expected = [
            'ffmpeg',
            '-i', '/tmp/input.mp4',
            '-map', '0:v',
            '-c:v', 'libx264',
            '-map', '0:a',
            '-c:a', 'aac',
            '-f', 'tee',
            '[f=hls:hls_time=2]http://ya.ru/1.m3u8|'
            '[f=hls:hls_list_size=5]http://ya.ru/2.m3u8'
        ]
        self.assertEqual(ff.get_args(), ensure_binary(expected))
