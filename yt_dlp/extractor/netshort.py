import urllib.parse

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    clean_html,
    float_or_none,
    int_or_none,
    parse_count,
    url_or_none,
)
from ..utils.traversal import traverse_obj


class NetShortBaseIE(InfoExtractor):
    _BASE_URL = 'https://netshort.com'

    def _extract_page_data(self, url, display_id):
        webpage = self._download_webpage(url, display_id)
        page_data = traverse_obj(self._search_nextjs_v13_data(webpage, display_id), (
            lambda _, v: v['shortPlayDetailVo']['shortPlayId'], any))
        if not page_data:
            raise ExtractorError('Unable to extract page data')
        return page_data

    @staticmethod
    def _extract_series_info(series):
        return traverse_obj(series, {
            'series': ('shortPlayName', {str}),
            'series_id': ('shortPlayId', {str}),
            'description': ('shotIntroduce', {clean_html}),
            'tags': ('shortPlayLabels', {dict.keys}, ..., {str}),
            'like_count': ('totalLikeNums', {parse_count}),
        })


class NetShortIE(NetShortBaseIE):
    IE_NAME = 'netshort'
    _VALID_URL = r'https?://(?:www\.)?netshort\.com/(?:[a-z]{2}/)?episode/(?P<id>(?:[^/?#]+-)?\d{15,}(?:-ep-\d+)?)/?(?:[?#]|$)'
    _TESTS = [{
        'url': 'https://netshort.com/episode/the-dragons-silly-captive-2112388670085812226',
        'info_dict': {
            'id': '2112439949717819394',
            'display_id': 'the-dragons-silly-captive-2112388670085812226',
            'ext': 'mp4',
            'title': "The Dragon's Silly Captive EP 1",
            'description': 'md5:add3adbbe6c7d2e59b6100dfcf63a4db',
            'episode': 'Episode 1',
            'episode_number': 1,
            'episode_id': '2112439949717819394',
            'series': "The Dragon's Silly Captive",
            'series_id': '2112388670085812226',
            'duration': 272.5,
            'timestamp': 1792494049,
            'upload_date': '20261020',
            'tags': ['Substitute Bride', 'Contract Lovers', 'Alternate History'],
            'like_count': int,
            'thumbnail': r're:https://awscover\.netshort\.com/.+',
        },
    }, {
        'url': 'https://netshort.com/episode/the-dragons-silly-captive-2112388670085812226-ep-2',
        'info_dict': {
            'id': '2112439949755572226',
            'display_id': 'the-dragons-silly-captive-2112388670085812226-ep-2',
            'ext': 'mp4',
            'title': "The Dragon's Silly Captive EP 2",
            'description': 'md5:add3adbbe6c7d2e59b6100dfcf63a4db',
            'episode': 'Episode 2',
            'episode_number': 2,
            'episode_id': '2112439949755572226',
            'series': "The Dragon's Silly Captive",
            'series_id': '2112388670085812226',
            'duration': float,
            'timestamp': int,
            'upload_date': str,
            'tags': 'count:3',
            'like_count': int,
            'thumbnail': r're:https://awscover\.netshort\.com/.+',
        },
        'params': {'skip_download': True},
    }, {
        'url': 'https://netshort.com/es/episode/la-cautiva-inocente-domó-al-dragón-2112388670136143874',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        display_id = urllib.parse.unquote(self._match_id(url))
        page_data = self._extract_page_data(url, display_id)
        episode = traverse_obj(page_data, ('initialCurrentEpisodeInfo', {dict})) or {}
        episode_id = episode.get('episodeId')
        if not episode_id:
            raise ExtractorError('Unable to extract episode info')
        if episode.get('isLock') and not episode.get('playVoucher'):
            raise ExtractorError('This episode is locked and requires purchase', expected=True)

        series_info = self._extract_series_info(page_data['shortPlayDetailVo'])
        episode_number = int_or_none(episode.get('episodeNo'))
        return {
            'id': episode_id,
            'display_id': display_id,
            'url': url_or_none(episode.get('playVoucher')),
            'ext': 'mp4',
            **series_info,
            'title': f'{series_info.get("series")} EP {episode_number}',
            'episode_id': episode_id,
            **traverse_obj(episode, {
                'episode_number': ('episodeNo', {int_or_none}),
                'duration': ('duration', {float_or_none}),
                'timestamp': ('publishTime', {int_or_none(scale=1000)}),
                'thumbnail': (('episodeWebCover', 'episodeCover'), {url_or_none}, any),
            }),
        }


class NetShortSeriesIE(NetShortBaseIE):
    IE_NAME = 'netshort:series'
    _VALID_URL = r'https?://(?:www\.)?netshort\.com/(?P<locale>[a-z]{2}/)?full-episodes/(?P<id>(?:[^/?#]+-)?\d{15,})/?(?:[?#]|$)'
    _TESTS = [{
        'url': 'https://netshort.com/full-episodes/the-dragons-silly-captive-2112388670085812226',
        'info_dict': {
            'id': '2112388670085812226',
            'title': "The Dragon's Silly Captive",
            'description': 'md5:add3adbbe6c7d2e59b6100dfcf63a4db',
        },
        'playlist_count': 40,
    }]

    def _real_extract(self, url):
        locale, display_id = self._match_valid_url(url).group('locale', 'id')
        display_id = urllib.parse.unquote(display_id)
        page_data = self._extract_page_data(
            f'{self._BASE_URL}/{locale or ""}episode/{display_id}', display_id)
        series = page_data['shortPlayDetailVo']
        episode_base_url = urllib.parse.urljoin(self._BASE_URL, series['shortPlayUrl'])

        entries = [
            self.url_result(
                episode_base_url if episode_no == 1 else f'{episode_base_url}-ep-{episode_no}', NetShortIE)
            for episode_no in traverse_obj(series, ('videoEpisodeInfos', ..., 'episodeNo', {int_or_none}))]
        return self.playlist_result(
            entries, series['shortPlayId'], series.get('shortPlayName'), clean_html(series.get('shotIntroduce')))
