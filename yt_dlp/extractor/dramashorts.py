import json
import re

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    clean_html,
    float_or_none,
    int_or_none,
    join_nonempty,
    parse_iso8601,
    parse_m3u8_attributes,
    url_or_none,
)
from ..utils.traversal import traverse_obj


class DramaShortsBaseIE(InfoExtractor):
    _API_BASE = 'https://web-api.dramashorts.io/v1'
    _VALID_URL_BASE = r'https?://(?:www\.)?dramashorts\.io/(?:[a-z]{2}/)?shorts/(?P<series_id>[0-9a-f-]{36})'

    def _call_api(self, endpoint, video_id, data, note='Downloading API JSON'):
        return self._download_json(
            f'{self._API_BASE}/{endpoint}', video_id, note, data=json.dumps({'data': data}).encode(),
            headers={
                'Content-Type': 'application/json',
                'X-OS': 'web',
                'X-OS-Version': '1.0.0',
                'X-App-Version': '1.0.0',
            })['result']

    def _get_series_info(self, series_id):
        movie = self._call_api(
            'web-movie-get', series_id, {'movie_id': series_id}, 'Downloading series info')['movie']
        return traverse_obj(movie, {
            'series': ('title', {str}),
            'series_id': ('id', {str}),
            'description': ('description', {clean_html}),
            'age_limit': ('age_maturity', {int_or_none}),
            'genres': ('genre', 'title', {str}, all, filter),
            'tags': ('tags', ..., 'title', {str}),
            'release_timestamp': ('release_date', {parse_iso8601}),
            'view_count': ('views_count', {int_or_none}),
            'like_count': ('likes_count', {int_or_none}),
        })

    def _get_episodes(self, series_id):
        return self._call_api(
            'web-episode-list', series_id, {'movie_id': series_id}, 'Downloading episode list')


class DramaShortsIE(DramaShortsBaseIE):
    IE_NAME = 'dramashorts'
    _VALID_URL = DramaShortsBaseIE._VALID_URL_BASE + r'/episode-(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://dramashorts.io/shorts/dd022264-9066-4ae7-8cd2-899b48e13b24/episode-1',
        'info_dict': {
            'id': '774c49bb-ba8d-4eea-a477-f0afd9b61261',
            'ext': 'mp4',
            'title': 'Wrong Jacket, Right Girl Episode 1',
            'description': 'md5:e7fd6bf2d7c573aee464a9a702593cf4',
            'episode': 'Episode 1',
            'episode_number': 1,
            'episode_id': '774c49bb-ba8d-4eea-a477-f0afd9b61261',
            'series': 'Wrong Jacket, Right Girl',
            'series_id': 'dd022264-9066-4ae7-8cd2-899b48e13b24',
            'duration': 115.291664,
            'age_limit': 18,
            'genres': ['LGBTQ+'],
            'tags': 'count:13',
            'release_timestamp': 1787616000,
            'release_date': '20260825',
            'view_count': int,
            'like_count': int,
            'thumbnail': r're:https://cdn\.dramashorts\.io/img/episodes-previews/.+\.jpeg',
        },
        'params': {'skip_download': 'm3u8'},
    }, {
        'url': 'https://dramashorts.io/fr/shorts/dd022264-9066-4ae7-8cd2-899b48e13b24/episode-2',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        series_id, episode_number = self._match_valid_url(url).group('series_id', 'id')
        episode_number = int(episode_number)

        episode_info = traverse_obj(self._get_episodes(series_id), (
            lambda _, v: v['episode']['index'] == episode_number, 'episode', any))
        if not episode_info:
            raise ExtractorError(f'Episode {episode_number} not found', expected=True)
        episode_id = episode_info['id']

        access = self._call_api(
            'web-episode-access', episode_id, {'movie_id': series_id, 'episode_id': episode_id},
            'Downloading episode access info')
        if access.get('type') == 'paywall':
            raise ExtractorError('This episode is locked behind a paywall', expected=True)
        m3u8_url = traverse_obj(access, ('payload', 'video_url', {url_or_none}))
        if not m3u8_url:
            raise ExtractorError('Unable to extract video URL')

        m3u8_doc = self._download_webpage(m3u8_url, episode_id, 'Downloading m3u8 information')
        formats, subtitles = self._parse_m3u8_formats_and_subtitles(
            m3u8_doc, m3u8_url, 'mp4', m3u8_id='hls', video_id=episode_id)
        # The m3u8 parser ignores DEFAULT=YES, so prefer the original audio track explicitly
        default_lang = traverse_obj(
            map(parse_m3u8_attributes, re.findall(r'#EXT-X-MEDIA:(.+)', m3u8_doc)),
            (lambda _, v: v['TYPE'] == 'AUDIO' and v['DEFAULT'] == 'YES', 'LANGUAGE', any))
        for fmt in formats:
            if fmt.get('vcodec') == 'none' and fmt.get('language'):
                fmt['language_preference'] = 10 if fmt['language'] == default_lang else -1
        series_info = self._get_series_info(series_id)

        return {
            'id': episode_id,
            'formats': formats,
            'subtitles': subtitles,
            **series_info,
            'title': join_nonempty(series_info.get('series'), episode_info.get('title'), delim=' '),
            'episode_id': episode_id,
            'episode_number': episode_number,
            **traverse_obj(episode_info, {
                'episode': ('title', {str}),
                'duration': ('duration', {float_or_none}),
                'thumbnail': ('cover_url', {url_or_none}),
            }),
        }


class DramaShortsSeriesIE(DramaShortsBaseIE):
    IE_NAME = 'dramashorts:series'
    _VALID_URL = DramaShortsBaseIE._VALID_URL_BASE + r'/?(?:[?#]|$)'
    _TESTS = [{
        'url': 'https://dramashorts.io/shorts/dd022264-9066-4ae7-8cd2-899b48e13b24',
        'info_dict': {
            'id': 'dd022264-9066-4ae7-8cd2-899b48e13b24',
            'title': 'Wrong Jacket, Right Girl',
            'description': 'md5:e7fd6bf2d7c573aee464a9a702593cf4',
        },
        'playlist_mincount': 31,
    }]

    def _entries(self, series_id, episodes):
        for index in traverse_obj(episodes, (..., 'episode', 'index', {int})):
            yield self.url_result(
                f'https://dramashorts.io/shorts/{series_id}/episode-{index}', DramaShortsIE)

    def _real_extract(self, url):
        series_id = self._match_valid_url(url).group('series_id')
        series_info = self._get_series_info(series_id)
        return self.playlist_result(
            self._entries(series_id, self._get_episodes(series_id)), series_id,
            series_info.get('series'), series_info.get('description'))
