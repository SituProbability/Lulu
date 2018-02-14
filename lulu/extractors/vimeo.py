#!/usr/bin/env python

import re
import json
import urllib.error
import urllib.parse

from lulu.common import (
    match1,
    urls_size,
    get_content,
    general_m3u8_extractor,
)
from lulu.util import log
from lulu.config import FAKE_HEADERS
from lulu.extractor import VideoExtractor


__all__ = [
    'vimeo_download', 'vimeo_download_by_id', 'vimeo_download_by_channel',
    'vimeo_download_by_channel_id'
]
site_info = 'Vimeo.com'


access_token = 'f6785418277b72c7c87d3132c79eec24'  # By Beining


class VimeoExtractor(VideoExtractor):
    stream_types = [
        {'id': '2160p', 'video_profile': '3840x2160'},
        {'id': '1440p', 'video_profile': '2560x1440'},
        {'id': '1080p', 'video_profile': '1920x1080'},
        {'id': '720p', 'video_profile': '1280x720'},
        {'id': '540p', 'video_profile': '960x540'},
        {'id': '360p', 'video_profile': '640x360'}
    ]
    name = 'Vimeo'

    def prepare(self, **kwargs):
        headers = FAKE_HEADERS.copy()
        if 'referer' in kwargs:
            headers['Referer'] = kwargs['referer']

        try:
            page = get_content('https://vimeo.com/{}'.format(self.vid))
            cfg_patt = r'clip_page_config\s*=\s*(\{.+?\});'
            cfg = json.loads(match1(page, cfg_patt))
            video_page = get_content(
                cfg['player']['config_url'], headers=headers
            )
            self.title = cfg['clip']['title']
            info = json.loads(video_page)
        except Exception as e:
            page = get_content('https://player.vimeo.com/video/{}'.format(
                self.vid
            ))
            self.title = match1(page, r'<title>([^<]+)</title>')
            info = json.loads(match1(page, r'var t=(\{.+?\});'))

        plain = info['request']['files']['progressive']
        for s in plain:
            meta = dict(src=[s['url']], container='mp4')
            meta['video_profile'] = '{}x{}'.format(s['width'], s['height'])
            for stream in self.__class__.stream_types:
                if s['quality'] == stream['id']:
                    self.streams[s['quality']] = meta
        self.master_m3u8 = info['request']['files']['hls']['cdns']

    def extract(self, **kwargs):
        for s in self.streams:
            self.streams[s]['size'] = urls_size(self.streams[s]['src'])

        master_m3u8s = []
        for m in self.master_m3u8:
            master_m3u8s.append(self.master_m3u8[m]['url'])

        master_content = None
        master_url = None

        for master_u in master_m3u8s:
            try:
                master_content = get_content(master_u).split('\n')
            except urllib.error.URLError:
                continue
            else:
                master_url = master_u

        if master_content is None:
            return

        lines = []
        for line in master_content:
            if len(line.strip()) > 0:
                lines.append(line.strip())

        pos = 0
        while pos < len(lines):
            if lines[pos].startswith('#EXT-X-STREAM-INF'):
                patt = 'RESOLUTION=(\d+)x(\d+)'
                hit = re.search(patt, lines[pos])
                if hit is None:
                    continue
                # width = hit.group(1)
                height = hit.group(2)

                if height in ('2160', '1440'):
                    m3u8_url = urllib.parse.urljoin(master_url, lines[pos+1])
                    meta = dict(m3u8_url=m3u8_url, container='m3u8')
                    if height == '1440':
                        meta['video_profile'] = '2560x1440'
                    else:
                        meta['video_profile'] = '3840x2160'
                    meta['size'] = 0
                    meta['src'] = general_m3u8_extractor(m3u8_url)
                    self.streams[height+'p'] = meta

                pos += 2
            else:
                pos += 1
        self.streams_sorted = []
        for stream_type in self.stream_types:
            if stream_type['id'] in self.streams:
                item = [('id', stream_type['id'])] + list(
                    self.streams[stream_type['id']].items()
                )
                self.streams_sorted.append(dict(item))


def vimeo_download_by_channel(url, info_only=False, **kwargs):
    """str->None
    """
    # https://vimeo.com/channels/464686
    channel_id = match1(url, r'https?://vimeo.com/channels/(\w+)')
    vimeo_download_by_channel_id(channel_id, info_only, **kwargs)


def vimeo_download_by_channel_id(channel_id, info_only=False, **kwargs):
    """str/int->None
    """
    html = get_content(
        'https://api.vimeo.com/channels/{channel_id}/videos?access_token='
        '{access_token}'.format(
            channel_id=channel_id, access_token=access_token
        )
    )
    data = json.loads(html)
    id_list = []

    for i in data['data']:
        id_list.append(match1(i['uri'], r'/videos/(\w+)'))

    for _id in id_list:
        try:
            vimeo_download_by_id(_id, None, info_only, **kwargs)
        except urllib.error.URLError as e:
            log.w('{} failed with {}'.format(id, e))


def vimeo_download_by_id(_id, title=None, info_only=False, **kwargs):
    # https://vimeo.com/58388167
    site = VimeoExtractor()
    site.download_by_vid(_id, info_only=info_only, **kwargs)


def vimeo_download(url, info_only=False, **kwargs):
    if re.match(r'https?://vimeo.com/channels/\w+', url):
        vimeo_download_by_channel(url, info_only, **kwargs)
    else:
        _id = match1(url, r'https?://[\w.]*vimeo.com[/\w]*/(\d+)')
        if _id is None:
            video_page = get_content(url)
            _id = match1(video_page, r'"clip_id":(\d+)')
        assert _id

        vimeo_download_by_id(_id, None, info_only=info_only, **kwargs)


download = vimeo_download
download_playlist = vimeo_download_by_channel
