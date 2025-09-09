// const name="홍길동";
// return (
//     <div>
//         <h1>안녕하세요, {name}!</h1>
//     </div>
// );

// function method(){
//     const a=3, b=5;
//     return (
//         <p>
//             {a}+{b}={a+b}
//         </p>
//     );
// }

// const student=17;
// return (
//     <p>
//         {student<20 ? "학생입니다." : "성인입니다."}
//     </p>
// );

// const fruits=['망고','딸기','거봉'];
// function FruitList() {
//     return (
//         <ul>
//             {fruits.map(fruit,index => (
//                 <li key={index}>{fruit}</li>
//             ))}
//         </ul>
//     );
// }

// function Greeting(props) {
//     return (
//         <div>
//             <h2>안녕하세요, {props.name}님!</h2>
//             <p>나이 : {props.age}세</p>
//         </div>
//     );
// }
// function App() {
//     return (
//         <div>
//             <Greeting name="홍길동" age={20} />
//             <Greeting name="김철수" age={25} />
//         </div>
//     );
// }

// function Welcome(props){
//     return <h1>hello, {props.name}!</h1>;
// }

// <Welcome name="철수" />

// function Wrapper(props){
//     return <div className="Wrapper">{props.children}</div>;
// }
// <Wrapper>
//     <p>안의 내용</p>
//     <button>button</button>
// </Wrapper>

// import {useState} from "react";
// function UserProfile(){
//     const [name, setName]=useState("");
//     const [age,setAge]=useState(20);
//     const [isStudent, setIsStudent]=useState(true);
//     return (
//         <div>
//             <input
//             value={name}
//             onChange={e=>setName(e.target.value)}
//             />
//             <button onClick={()=>setAge(age+1)}>나이증가</button>
//             <button onClick={()=>setIsStudent(!isStudent)}>학생여부전환</button>
//         </div>
//     );
// }


//연습문제1번
import React from 'react';
function FruitList(props){
    return (
        <div>
            <ul>
                {props.fruits.map((fruit, index)=>(
                    <li key={index}>{fruit}</li>
                ))}
            </ul>
        </div>
    );
}
<FruitList fruits={['망고','딸기','거봉']} />
//export default FruitList;


//연습문제2번
import React, {useState} from 'react'; 
function ColorText(){
    const [textColor, setTextColor]=useState('black');
    const changeColor=() =>{
        setTextColor(textColor==='black'? 'red':'black');
    };
    return (
        <div>
            <p style={{color : textColor}}>이 텍스트의 색상이 바뀝니다.</p>
            <button onClick={changeColor}>색상변경</button>
        </div>
    );
}
//export default ColorText;