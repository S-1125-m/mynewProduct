from flask import Flask, render_template, request
import pandas as pd
import random
from scipy.spatial import distance
import logging
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Spotify APIの認証設定
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id="e2777415026043b89f676d90ef19460e",
    client_secret="3fd9d46502764ff3ba0ae01aea46c046",
    redirect_uri="http://localhost:4481/",
    scope="playlist-modify-public user-modify-playback-state"
))

app = Flask(__name__, static_folder='static', template_folder='templates')

# CSVファイルの読み込み
file_path = 'spotify_album_features_with_popularity.csv'
songs_df = pd.read_csv(file_path).dropna(axis=1, how='all')

import logging

# ログ設定
logging.basicConfig(level=logging.DEBUG)

# ログ出力例
logging.debug("CSVファイルを正常に読み込みました。")


# 気分候補の再定義（4つの特徴で分類）
mood_definitions = {
    "joyful": {"energy": 0.8, "danceability": 0.8, "valence": 0.9, "tempo": 0.45},
    "peaceful": {"energy": 0.3, "danceability": 0.4, "valence": 0.6, "tempo": 0.25},
    "melancholic": {"energy": 0.4, "danceability": 0.3, "valence": 0.3, "tempo": 0.16},
    "uplifting": {"energy": 0.7, "danceability": 0.7, "valence": 0.8, "tempo": 0.50},
    "nostalgic": {"energy": 0.5, "danceability": 0.4, "valence": 0.4, "tempo": 0.36},
    "romantic": {"energy": 0.6, "danceability": 0.5, "valence": 0.7, "tempo": 0.30},
    "dramatic": {"energy": 0.9, "danceability": 0.6, "valence": 0.5, "tempo": 0.58},
    "calm": {"energy": 0.2, "danceability": 0.3, "valence": 0.5, "tempo": 0.18},
    "energetic": {"energy": 0.95, "danceability": 0.9, "valence": 0.8, "tempo": 0.60},
    "sad": {"energy": 0.3, "danceability": 0.2, "valence": 0.2, "tempo": 0.15},
}
# Periodマッピング
period_mapping = {
    "バロック": (1600, 1750),
    "バロック後期": (1730, 1770),
    "古典派": (1750, 1827),
    "古典派後期": (1800, 1840),
    "ロマン派前期": (1827, 1850),
    "ロマン派中期": (1840, 1870),
    "ロマン派後期": (1850, 1900),
    "印象派": (1870, 1920),
    "近現代": (1900, 2024)
}

# 指定された年に該当するすべてのperiodを取得
def find_periods_by_year(year):
    return [period for period, (start, end) in period_mapping.items() if start <= year <= end]

# 曲をシャッフルしてプレイリストを作成
def create_playlist(songs, target_duration):
    random.shuffle(songs)
    selected_songs = []
    total_duration = 0

    for song in songs:
        if total_duration + song["duration_ms"] <= target_duration:
            selected_songs.append(song)
            total_duration += song["duration_ms"]

    return selected_songs, total_duration

def play_playlist(playlist_uri):
    """Spotifyでプレイリストを自動再生"""
    try:
        devices = sp.devices()
        if not devices['devices']:
            print("Spotifyデバイスが見つかりません。アクティブなデバイスを確認してください。")
            return False

        device_id = devices['devices'][0]['id']
        sp.start_playback(device_id=device_id, context_uri=playlist_uri)
        return True
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return False

# プレイリスト候補生成
def generate_playlists(songs_df, target_duration, num_candidates=5):
    songs = songs_df.to_dict(orient="records")
    playlists = []

    for i in range(num_candidates):
        playlist, total_duration = create_playlist(songs, target_duration)

        if playlist:
            track_ids = [song['id'] for song in playlist if song.get('id')]

            if track_ids:
                playlist_url = create_spotify_playlist(
                    f"Piano Playlist {i+1}", track_ids
                )
                playlist_id = playlist_url.split("/")[-1].split("?")[0]
                playlist_uri = f"spotify:playlist:{playlist_id}"

                # 自動再生を試行
                if play_playlist(playlist_uri):
                    print(f"プレイリスト {playlist_url} を生成中・・・")
                else:
                    print(f"プレイリスト {playlist_url} の再生に失敗しました。")

                playlists.append({
                    "playlist": playlist,
                    "total_duration": total_duration,
                    "spotify_link": playlist_url
                })
            else:
                print("トラックIDが見つかりません。")

    return playlists
    
def create_spotify_playlist(name, track_ids):
    """ Spotifyでプレイリストを作成し、曲を追加 """
    user_id = sp.me()['id']

    # プレイリストの作成
    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=True,
        description="自動生成されたプレイリスト"
    )

    # プレイリストにトラックを追加
    sp.playlist_add_items(playlist_id=playlist['id'], items=track_ids)

    # プレイリストのリンクを返す
    return playlist['external_urls']['spotify']


# 曲をフィルタリング
def filter_songs(df, year=None, artist=None, sliders=None):
    filtered_df = df.copy()

    # フィルタリング前
    print("フィルタリング開始。年:", year, "作曲家:", artist, "スライダー:", sliders)


    # 年代フィルタリング
    if year:
        matching_periods = find_periods_by_year(year)
        filtered_df = filtered_df[filtered_df['period'].isin(matching_periods)]

    # 作曲家名フィルタリング
    if artist:
        filtered_df = filtered_df[
            filtered_df['artist_name'].str.contains(artist, case=False, na=False)
        ]

    # スライダーによるフィルタリング
    if sliders:
        if "energy" in sliders:
            filtered_df = filtered_df[
                (filtered_df['energy'] >= sliders['energy'] - 0.1) &
                (filtered_df['energy'] <= sliders['energy'] + 0.1)
            ]
        if "valence" in sliders:
            filtered_df = filtered_df[
                (filtered_df['valence'] >= sliders['valence'] - 0.1) &
                (filtered_df['valence'] <= sliders['valence'] + 0.1)
            ]
        if "danceability" in sliders:
            filtered_df = filtered_df[
                (filtered_df['danceability'] >= sliders['danceability'] - 0.1) &
                (filtered_df['danceability'] <= sliders['danceability'] + 0.1)
            ]
        if "tempo" in sliders:
            filtered_df = filtered_df[
                (filtered_df['tempo'] >= sliders['tempo'] - 0.1) &
                (filtered_df['tempo'] <= sliders['tempo'] + 0.1)
            ]
        if "duration_ms" in sliders:
            filtered_df = filtered_df[
                (filtered_df['duration_ms'] >= sliders['duration_ms'] - 100000) &
                (filtered_df['duration_ms'] <= sliders['duration_ms'] + 100000)
            ]

    return filtered_df

    # フィルタリング結果
    print("フィルタリング後の曲数:", len(filtered_df))


#条件に最も近い曲を取得する
def find_closest_songs(df, target_params, top_n=10):
    """
    条件に最も近い曲を取得する
    """
    if df.empty:
        return []
    
    # ターゲットパラメータを用いて距離を計算
    df['distance'] = df.apply(
        lambda row: distance.euclidean(
            [row['energy'], row['valence'], row['danceability'], row['tempo']],
            [target_params['energy'], target_params['valence'], target_params['danceability'], target_params['tempo']]
        ),
        axis=1
    )
    # 距離が近い順にソートしてトップN件を返す
    closest_songs = df.nsmallest(top_n, 'distance').drop(columns=['distance'])
    return closest_songs



# 気分の自動推定
def get_closest_mood(sliders):
    min_dist = float('inf')
    best_mood = None

    for mood, params in mood_definitions.items():
        mood_vector = [params['energy'], params['danceability'], params['valence'], params['tempo']]
        user_vector = [sliders['energy'], sliders['danceability'], sliders['valence'], sliders['tempo']]
        dist = distance.euclidean(mood_vector, user_vector)

        if dist < min_dist:
            min_dist = dist
            best_mood = mood

    return best_mood

@app.route('/')
def index():
    return render_template('index2.html')

@app.route('/recommend', methods=['POST'])
def recommend():
    global songs_df

    # ユーザー入力を取得
    year = int(request.form.get('year')) if request.form.get('year') else None
    artist = request.form.get('artist')
    sliders = {
        "エネルギー": float(request.form.get('energy')),
        "明るさ": float(request.form.get('valence')),
        "ダンスのしやすさ": float(request.form.get('danceability')),
        "テンポ": float(request.form.get('tempo')),
        "1曲あたりの長さ": int(request.form.get('duration_ms')),
    }
    target_duration = int(request.form.get('target_duration')) * 60000 if request.form.get('target_duration') else 1800000
    num_candidates = int(request.form.get('num_candidates', 3)) # デフォルトで3候補

    playlists = []

    # フィルタリング処理
    filtered_songs = filter_songs(songs_df, year, artist, sliders)
    print(filtered_songs)

    # 曲が見つからない場合は条件に最も近い曲を探す
    if filtered_songs.empty:
        print("フィルタリングされた曲が見つかりません。条件に最も近い曲を検索します。")
        filtered_songs = find_closest_songs(songs_df, sliders, top_n=50)
        playlists = generate_playlists(filtered_songs, target_duration, num_candidates)

        # プレイリストにインデックスを追加
        playlists = [
            {"index": idx + 1, "playlist": p["playlist"], "total_duration": p["total_duration"], "spotify_link": p["spotify_link"]}
            for idx, p in enumerate(playlists)
        ]
        print(f"最も近い曲の数: {len(filtered_songs)}")

    if not filtered_songs.empty:
        playlists = generate_playlists(filtered_songs, target_duration, num_candidates)
        # プレイリストにインデックスを追加
        playlists = [
            {"index": idx + 1, "playlist": p["playlist"], "total_duration": p["total_duration"], "spotify_link": p["spotify_link"]}
            for idx, p in enumerate(playlists)
        ]

    # Spotifyリンクの生成
    for playlist in playlists:
        track_ids = [song['id'] for song in playlist['playlist']]
        if track_ids:
            spotify_urls = [
                f"https://open.spotify.com/track/{track_id}?autoplay=true" for track_id in track_ids
            ]
            playlist['spotify_links'] = spotify_urls
        else:
            playlist['spotify_links'] = []
        
            

    return render_template('results2.html', playlists=playlists, songs=filtered_songs.to_dict(orient="records"))

# スライダー値受信ルートの追加
@app.route('/update_mood', methods=['POST'])
def update_mood():
    sliders = {
        "energy": float(request.form.get('energy')),
        "danceability": float(request.form.get('danceability')),
        "valence": float(request.form.get('valence')),
        "tempo": float(request.form.get('tempo'))
    }
    detected_mood = get_closest_mood(sliders)
    return render_template('index2.html', detected_mood=detected_mood)


if __name__ == '__main__':
    app.run(debug=True) 