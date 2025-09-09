import React, {useState} from 'react';
function ProfileCard(props){
    const [likeCount, setLikeCount]=useState(0);
    const handleLike=()=>{
        <p textAlign="right" onClick={()=> setLikeCount(likeCount+1)}>좋아요 {likeCount}개</p>
    }
    return (
        <div className="profile-card">
            <img src="profile.jpg" />
            <h1>{props.name}</h1>
            <p>학번 : {props.studentId}</p>
            <p>전공 : {props.major}</p>
            <p>안녕하세요! React 컴포넌트를 배우고 잇는 {props.name}입니다.</p>
            <button onClick={handleLike}>좋아요</button>
        </div>
    )
}
<ProfileCard name="강우성" studentId="2022108129" major="인공지능학과" />